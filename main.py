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
import sv_ttk

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

def create_anki_package(
    input_text: str,
    log_callback=print,
    model_name: str = "openai-fast",
    deck_name: str = "Generated Chinese Cards",
):
    """Generates an Anki package (.apkg) for the given word(s)."""
    # Split input by standard comma, Chinese comma, or newline
    words = [w.strip() for w in re.split(r'[,，\n]', input_text) if w.strip()]
    
    if not words:
        log_callback("No valid words found.")
        return

    # Create Deck
    deck = genanki.Deck(DECK_ID, deck_name)
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
    root.geometry("600x650")  # Increased height for better layout

    # Style
    style = ttk.Style()
    style.configure("TButton", font=("Segoe UI", 12))  # Cross-platform friendly font
    style.configure("TLabel", font=("Segoe UI", 11))
    style.configure("Header.TLabel", font=("Segoe UI", 12, "bold"))

    # Main Container with padding
    main_frame = ttk.Frame(root, padding="20")
    main_frame.pack(fill=tk.BOTH, expand=True)

    # --- Header ---
    header_label = ttk.Label(main_frame, text="Generate Anki Cards", style="Header.TLabel")
    header_label.pack(anchor=tk.W, pady=(0, 10))

    # --- Input Section ---
    input_frame = ttk.LabelFrame(main_frame, text="Input", padding="10")
    input_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    input_instruction = ttk.Label(input_frame, text="Enter Chinese words (one per line, or comma separated):")
    input_instruction.pack(anchor=tk.W, pady=(0, 5))

    word_entry = tk.Text(input_frame, height=8, font=("Arial", 14), wrap=tk.WORD)
    word_entry.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
    
    # Scrollbar for input
    scrollbar = ttk.Scrollbar(input_frame, orient="vertical", command=word_entry.yview)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)  # Use pack inside frame, need to repack text to respect side? 
    # Actually, let's repack to do it right:
    word_entry.pack_forget()
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    word_entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    word_entry['yscrollcommand'] = scrollbar.set

    word_entry.focus()

    # --- Settings Section ---
    settings_frame = ttk.LabelFrame(main_frame, text="Settings", padding="10")
    settings_frame.pack(fill=tk.X, pady=(0, 10))

    # Grid layout for settings
    settings_frame.columnconfigure(1, weight=1)

    # Deck Name
    ttk.Label(settings_frame, text="Deck Name:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10), pady=5)
    deck_var = tk.StringVar(value="Generated Chinese Cards")
    deck_entry = ttk.Entry(settings_frame, textvariable=deck_var, font=("Segoe UI", 11))
    deck_entry.grid(row=0, column=1, sticky=tk.EW, pady=5)

    # Model Selection
    ttk.Label(settings_frame, text="AI Model:").grid(row=1, column=0, sticky=tk.W, padx=(0, 10), pady=5)
    model_var = tk.StringVar(value="gemini")
    model_select = ttk.Combobox(settings_frame, textvariable=model_var, values=["gemini", "openai-fast"], state="readonly", font=("Segoe UI", 11))
    model_select.grid(row=1, column=1, sticky=tk.EW, pady=5)

    # Auto Import Checkbox
    auto_import_var = tk.BooleanVar(value=True)
    auto_import_check = ttk.Checkbutton(settings_frame, text="Auto-open .apkg file after generation", variable=auto_import_var)
    auto_import_check.grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(5, 0))

    # --- Actions Section ---
    action_frame = ttk.Frame(main_frame)
    action_frame.pack(fill=tk.X, pady=(0, 10))

    # Log Area (initially collapsed/small? No, visible is good)
    log_label = ttk.Label(main_frame, text="Status Log:")
    log_label.pack(anchor=tk.W, pady=(5, 0))

    log_area = scrolledtext.ScrolledText(main_frame, height=8, state='disabled', font=("Courier New", 11))
    log_area.pack(fill=tk.BOTH, expand=True)

    def log_message(message):
        log_area.config(state='normal')
        log_area.insert(tk.END, message + "\n")
        log_area.see(tk.END)
        log_area.config(state='disabled')

    def on_generate():
        # Get text from Text widget (1.0 to END-1c to avoid trailing newline)
        input_text = word_entry.get("1.0", "end-1c").strip()
        selected_model = model_var.get()
        selected_deck = deck_var.get().strip() or "Generated Chinese Cards"
        
        # Update global auto_import based on checkbox
        global auto_import
        auto_import = auto_import_var.get()

        if not input_text:
            messagebox.showwarning("Input Error", "Please enter at least one word.")
            return

        generate_btn.config(state=tk.DISABLED)
        word_entry.config(state=tk.DISABLED)
        # Clear log on new run? Optional. Let's add a separator.
        log_message("\n" + "=" * 40)
        log_message("Starting generation task...")
        
        def run_task():
            try:
                create_anki_package(
                    input_text,
                    log_callback=log_message,
                    model_name=selected_model,
                    deck_name=selected_deck,
                )
            except Exception as e:
                log_message(f"Error: {e}")
            finally:
                root.after(0, lambda: generate_btn.config(state=tk.NORMAL))
                root.after(0, lambda: word_entry.config(state=tk.NORMAL))

        threading.Thread(target=run_task, daemon=True).start()

    # Generate Button
    generate_btn = ttk.Button(action_frame, text="Generate Flashcards", command=on_generate, style="Accent.TButton") # Accent style if supported by sv_ttk
    generate_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

    # Clear Log Button
    def on_clear_log():
        log_area.config(state='normal')
        log_area.delete(1.0, tk.END)
        log_area.config(state='disabled')
        
    clear_btn = ttk.Button(action_frame, text="Clear Log", command=on_clear_log)
    clear_btn.pack(side=tk.RIGHT, fill=tk.X, expand=False) # Smaller clear button

    sv_ttk.set_theme("dark")
    root.mainloop()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "--gui":
            launch_gui()
        else:
            input_word = sys.argv[1]
            deck_name = sys.argv[2] if len(sys.argv) > 2 else "Generated Chinese Cards"
            create_anki_package(input_word, deck_name=deck_name)
    else:
        # Default to GUI mode if no args provided
        launch_gui()
