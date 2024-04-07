!pip install EbookLib

import time
import re
import os
from ebooklib import epub
import base64
import requests
import json

ANTHROPIC_API_KEY = "YOUR KEY HERE"
stability_api_key = "YOUR KEY HERE" # get it at https://beta.dreamstudio.ai/

def remove_first_line(test_string):
    if test_string.startswith("Here") and test_string.split("\n")[0].strip().endswith(":"):
        return re.sub(r'^.*\n', '', test_string, count=1)
    return test_string

def generate_text(prompt, model="claude-3-haiku-20240307", max_tokens=2000, temperature=0.7):
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    data = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "system": "You are a world-class author. Write the requested content with great skill and attention to detail.",
        "messages": [{"role": "user", "content": prompt}],
    }
    response = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=data)
    response_text = response.json()['content'][0]['text']
    return response_text.strip()

def generate_cover_prompt(plot):
    response = generate_text(f"Plot: {plot}\n\n--\n\nDescribe the cover we should create, based on the plot. This should be two sentences long, maximum.")
    return response

def generate_title(plot):
    response = generate_text(f"Here is the plot for the book: {plot}\n\n--\n\nRespond with a great title for this book. Only respond with the title, nothing else is allowed.")
    return remove_first_line(response)

def create_cover_image(plot):

  plot = str(generate_cover_prompt(plot))

  engine_id = "stable-diffusion-xl-beta-v2-2-2"
  api_host = os.getenv('API_HOST', 'https://api.stability.ai')
  api_key = stability_api_key

  if api_key is None:
      raise Exception("Missing Stability API key.")

  response = requests.post(
      f"{api_host}/v1/generation/{engine_id}/text-to-image",
      headers={
          "Content-Type": "application/json",
          "Accept": "application/json",
          "Authorization": f"Bearer {api_key}"
      },
      json={
          "text_prompts": [
              {
                  "text": plot
              }
          ],
          "cfg_scale": 7,
          "clip_guidance_preset": "FAST_BLUE",
          "height": 768,
          "width": 512,
          "samples": 1,
          "steps": 30,
      },
  )

  if response.status_code != 200:
      raise Exception("Non-200 response: " + str(response.text))

  data = response.json()

  for i, image in enumerate(data["artifacts"]):
      with open(f"/content/cover.png", "wb") as f: # replace this if running locally, to where you store the cover file
          f.write(base64.b64decode(image["base64"]))

def generate_chapter_title(chapter_content):
    response = generate_text(f"Chapter Content:\n\n{chapter_content}\n\n--\n\nGenerate a concise and engaging title for this chapter based on its content. Respond with the title only, nothing else.")
    return remove_first_line(response)

def create_epub(title, author, chapters, cover_image_path='cover.png'):
    book = epub.EpubBook()
    # Set metadata
    book.set_identifier('id123456')
    book.set_title(title)
    book.set_language('en')
    book.add_author(author)
    # Add cover image
    with open(cover_image_path, 'rb') as cover_file:
        cover_image = cover_file.read()
    book.set_cover('cover.png', cover_image)
    # Create chapters and add them to the book
    epub_chapters = []
    for i, chapter_content in enumerate(chapters):
        chapter_title = generate_chapter_title(chapter_content)
        chapter_file_name = f'chapter_{i+1}.xhtml'
        epub_chapter = epub.EpubHtml(title=chapter_title, file_name=chapter_file_name, lang='en')
        # Add paragraph breaks
        formatted_content = ''.join(f'<p>{paragraph.strip()}</p>' for paragraph in chapter_content.split('\n') if paragraph.strip())
        epub_chapter.content = f'<h1>{chapter_title}</h1>{formatted_content}'
        book.add_item(epub_chapter)
        epub_chapters.append(epub_chapter)


    # Define Table of Contents
    book.toc = (epub_chapters)

    # Add default NCX and Nav files
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # Define CSS style
    style = '''
    @namespace epub "http://www.idpf.org/2007/ops";
    body {
        font-family: Cambria, Liberation Serif, serif;
    }
    h1 {
        text-align: left;
        text-transform: uppercase;
        font-weight: 200;
    }
    '''

    # Add CSS file
    nav_css = epub.EpubItem(uid="style_nav", file_name="style/nav.css", media_type="text/css", content=style)
    book.add_item(nav_css)

    # Create spine
    book.spine = ['nav'] + epub_chapters

    # Save the EPUB file
    epub.write_epub(f'{title}.epub', book)


def generate_book(writing_style, book_description, num_chapters):
    print("Generating plot outline...")
    plot_prompt = f"Create a detailed plot outline for a {num_chapters}-chapter book in the {writing_style} style, based on the following description:\n\n{book_description}\n\nEach chapter should be at least 10 pages long."
    plot_outline = generate_text(plot_prompt)
    print("Plot outline generated.")

    chapters = []
    for i in range(num_chapters):
        print(f"Generating chapter {i+1}...")
        chapter_prompt = f"Previous Chapters:\n\n{' '.join(chapters)}\n\nWriting style: `{writing_style}`\n\nPlot Outline:\n\n{plot_outline}\n\nWrite chapter {i+1} of the book, ensuring it follows the plot outline and builds upon the previous chapters. The chapter should be at least 256 paragraphs long... we're going for lengthy yet exciting chapters here."
        chapter = generate_text(chapter_prompt, max_tokens=4000)
        chapters.append(remove_first_line(chapter))
        print(f"Chapter {i+1} generated.")
        time.sleep(1)  # Add a short delay to avoid hitting rate limits

    print("Compiling the book...")
    book = "\n\n".join(chapters)
    print("Book generated!")

    return plot_outline, book, chapters

# User input
writing_style = input("Enter the desired writing style: ")
book_description = input("Enter a high-level description of the book: ")
num_chapters = int(input("Enter the number of chapters: "))

# Generate the book
plot_outline, book, chapters = generate_book(writing_style, book_description, num_chapters)

title = generate_title(plot_outline)

# Save the book to a file
with open(f"{title}.txt", "w") as file:
    file.write(book)

create_cover_image(plot_outline)

# Create the EPUB file
create_epub(title, 'AI', chapters, '/content/cover.png')

print(f"Book saved as '{title}.txt'.")
