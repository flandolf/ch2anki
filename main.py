import subprocess
import sys
import os
import tempfile
import json
import genanki
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from g4f.client import ClientFactory
import re
import platform

auto_import = True

client = ClientFactory.create_client("pollinations")

# Anki Model Configuration
# Unique IDs (generated randomly, keep consistent for deck updates)
MODEL_ID = 1607392319
DECK_ID = 2059400110

# Define the card styling and fields
style = """
.card {
 font-family: arial;
 font-size: 20px;
 text-align: center;
 color: black;
 background-color: white;
}
.hanzi { font-size: 40px; font-weight: bold; color: #70BDFF; }
.pinyin { font-size: 24px; color: #70BDFF; }
.meaning { font-size: 20px; font-style: italic; }
.examples { text-align: left; margin-top: 20px; font-size: 16px; }
"""

cn_model = genanki.Model(
  MODEL_ID,
  'Chinese Vocab Model',
  fields=[
    {'name': 'Hanzi'},
    {'name': 'Pinyin'},
    {'name': 'Meaning'},
    {'name': 'Examples'},
  ],
  templates=[
    {
      'name': 'Card 1',
      'qfmt': '<div class="hanzi">{{Hanzi}}</div>',
      'afmt': '''{{FrontSide}}
                 <hr id="answer">
                 <div class="pinyin">{{Pinyin}}</div>
                 <div class="meaning">{{Meaning}}</div>
                 <div class="examples">{{Examples}}</div>''',
    },
  ],
  css=style
)

def get_batch_data(words: list, model_name: str = "openai-fast"):
    """Fetch structured data for a list of words using g4f."""
    words_str = ", ".join(words)
    prompt = f"""
    You are a Chinese language tutor. Create flashcards for the following words: {words_str}.
    
    RESPONSE FORMAT INSTRUCTIONS:
    You must output a valid JSON ARRAY only. Do not wrap the output in markdown code blocks.
    The output must be a list of objects, one for each word.
    
    Each object must have exactly these keys:
    - "hanzi": The input Chinese word.
    - "pinyin": The pinyin with tone marks.
    - "meaning": Concise English definition.
    - "examples": HTML string with exactly 2 examples formatted EXACTLY like this: "<b>Example 1:</b> HANZI<br>(PINYIN)<br>ENGLISH<br><br><b>Example 2:</b> HANZI<br>(PINYIN)<br>ENGLISH".
    """

    try:
        print(f"[DEBUG] Sending batch prompt for: {words_str} using model: {model_name}")
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            web_search=False
        )
        content = response.choices[0].message.content.strip()
        print(f"[DEBUG] Raw content received:\n{content}")
        
        # Clean up markdown if present
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
            
        cleaned_content = content.strip()
        print(f"[DEBUG] Cleaned content for JSON parsing:\n{cleaned_content}")
        parsed_data = json.loads(cleaned_content)
        
        # Ensure it's a list
        if isinstance(parsed_data, dict):
            return [parsed_data]
        return parsed_data
        
    except Exception as e:
        print(f"Error fetching data from AI: {e}", file=sys.stderr)
        return None

def create_anki_package(input_text: str, log_callback=print, model_name: str = "openai-fast"):
    """Generates an Anki package (.apkg) for the given word(s)."""
    # Split input by standard comma, Chinese comma, or newline
    words = [w.strip() for w in re.split(r'[,，\n]', input_text) if w.strip()]
    
    if not words:
        log_callback("No valid words found.")
        return

    # Create Deck
    deck = genanki.Deck(DECK_ID, 'Generated Chinese Cards')
    count = 0
    
    # Process in batches of 3
    BATCH_SIZE = 3
    
    for i in range(0, len(words), BATCH_SIZE):
        batch_words = words[i:i + BATCH_SIZE]
        log_callback(f"Processing batch: {', '.join(batch_words)} using {model_name}...")
        
        results = get_batch_data(batch_words, model_name=model_name)
        
        if not results:
            log_callback(f"Skipping batch {batch_words} (API error)")
            continue

        for data in results:
            hanzi = data.get('hanzi')
            # Fallback if Hanzi is missing from AI response (use one of the inputs if possible, but risky)
            if not hanzi:
                hanzi = batch_words[0] if len(batch_words) == 1 else "Unknown"

            log_callback(f"[DEBUG] Parsed item: {hanzi}")

            # Create Note
            note = genanki.Note(
              model=cn_model,
              fields=[
                  hanzi, 
                  data.get('pinyin', ''), 
                  data.get('meaning', ''), 
                  data.get('examples', '')
              ]
            )
            deck.add_note(note)
            count += 1

    if count == 0:
        log_callback("No cards generated.")
        return

    # Save package
    if count == 1:
        # Use simple name for single word
        # Sanitize filename
        safe_name = re.sub(r'[\\/*?:"<>|]', "", words[0])
        filename = f"{safe_name}.apkg"
    else:
        # Use batch name for multiple
        safe_name = re.sub(r'[\\/*?:"<>|]', "", words[0])
        filename = f"{safe_name}_batch_{count}.apkg"

    # Modify to save in temp directory
    filepath = os.path.join(tempfile.gettempdir(), filename)

    genanki.Package(deck).write_to_file(filepath)
    log_callback(f"Success! Saved {count} cards to: {filepath}")
    if auto_import:
        current_os = platform.system()
        if current_os == "Darwin":  # macOS
            subprocess.call(["open", filepath])
        else:  # Linux
            subprocess.call(["xdg-open", filepath])

def launch_gui():
    """Launches a Tkinter GUI for the application."""
    root = tk.Tk()
    root.title("Chinese to Anki Generator")
    root.geometry("500x400")
    # photo = tk.PhotoImage(file=r"/Users/andy/Projects/ch2anki/icon-512.png")
    # root.wm_iconphoto(False, photo)

    # Style
    style = ttk.Style()
    style.configure("TButton", font=("Arial", 12))
    style.configure("TLabel", font=("Arial", 12))

    # Main Frame
    main_frame = ttk.Frame(root, padding="20")
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Input Section
    input_label = ttk.Label(main_frame, text="Enter Chinese Word(s):")
    input_label.pack(anchor=tk.W, pady=(0, 5))

    word_entry = ttk.Entry(main_frame, font=("Arial", 14))
    word_entry.pack(fill=tk.X, pady=(0, 10))
    word_entry.focus()

    # Model Selection
    model_frame = ttk.Frame(main_frame)
    model_frame.pack(fill=tk.X, pady=(0, 10))
    
    ttk.Label(model_frame, text="Select Model:").pack(side=tk.LEFT, padx=(0, 10))
    
    model_var = tk.StringVar(value="openai-fast")
    model_select = ttk.Combobox(model_frame, textvariable=model_var, values=["openai-fast", "gemini"], state="readonly")
    model_select.pack(side=tk.LEFT, fill=tk.X, expand=True)

    # Log Area
    log_label = ttk.Label(main_frame, text="Status Log:")
    log_label.pack(anchor=tk.W, pady=(10, 5))

    log_area = scrolledtext.ScrolledText(main_frame, height=10, state='disabled', font=("Courier", 12))
    log_area.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    def log_message(message):
        log_area.config(state='normal')
        log_area.insert(tk.END, message + "\n")
        log_area.see(tk.END)
        log_area.config(state='disabled')

    def on_generate():
        word = word_entry.get().strip()
        selected_model = model_var.get()
        if not word:
            messagebox.showwarning("Input Error", "Please enter a word.")
            return

        generate_btn.config(state=tk.DISABLED)
        word_entry.config(state=tk.DISABLED)
        log_message("-" * 30)
        
        def run_task():
            try:
                create_anki_package(word, log_callback=log_message, model_name=selected_model)
            except Exception as e:
                log_message(f"Error: {e}")
            finally:
                root.after(0, lambda: generate_btn.config(state=tk.NORMAL))
                root.after(0, lambda: word_entry.config(state=tk.NORMAL))

        threading.Thread(target=run_task, daemon=True).start()

    # Generate Button
    generate_btn = ttk.Button(main_frame, text="Generate Flashcard", command=on_generate)
    generate_btn.pack(fill=tk.X, pady=10)

    # Clear Button
    def on_clear():
        log_area.config(state='normal')
        log_area.delete(1.0, tk.END)
        log_area.config(state='disabled')
    clear_btn = ttk.Button(main_frame, text="Clear Log", command=on_clear)
    clear_btn.pack(fill=tk.X)

    # Bind Enter key
    root.bind('<Return>', lambda event: on_generate())

    root.mainloop()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "--gui":
            launch_gui()
        else:
            input_word = sys.argv[1]
            create_anki_package(input_word)
    else:
        # Default to GUI mode if no args provided
        launch_gui()
