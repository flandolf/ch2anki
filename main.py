import subprocess
import sys
import os
import tempfile
import json
import dotenv
import genanki
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import re
import platform
import sv_ttk
import requests
auto_import = True
    
dotenv.load_dotenv()
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
    "Chinese Vocab Model",
    fields=[
        {"name": "Hanzi"},
        {"name": "Pinyin"},
        {"name": "Meaning"},
        {"name": "Examples"},
    ],
    templates=[
        {
            "name": "Card 1",
            "qfmt": '<div class="hanzi">{{Hanzi}}</div>',
            "afmt": """{{FrontSide}}
                 <hr id="answer">
                 <div class="pinyin">{{Pinyin}}</div>
                 <div class="meaning">{{Meaning}}</div>
                 <div class="examples">{{Examples}}</div>""",
        },
    ],
    css=style,
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

    CONTENT INSTRUCTIONS:
    - If the input word is a single character, the examples MUST be common phrases or compound words containing that character (e.g. if word is "好", examples could be "你好", "美好").
    - If the input word is a multi-character word, the examples should be sentences using the word.
    """

    try:
        print(
            f"[DEBUG] Sending batch prompt for: {words_str} using model: {model_name}"
        )
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {os.getenv('OPENROUTER_API')}",
                "Content-Type": "application/json",
            },
            data=json.dumps(
                {
                    "model": model_name,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                }
            ),
        )
        response_data = response.json()
        content = response_data["choices"][0]["message"]["content"]
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
    words = [w.strip() for w in re.split(r"[,，\n]", input_text) if w.strip()]

    if not words:
        log_callback("No valid words found.")
        return

    # Create Deck
    deck = genanki.Deck(DECK_ID, deck_name)
    count = 0

    # Process in batches of 10
    BATCH_SIZE = 10

    for i in range(0, len(words), BATCH_SIZE):
        batch_words = words[i : i + BATCH_SIZE]
        log_callback(
            f"Processing batch: {', '.join(batch_words)} using {model_name}..."
        )

        results = get_batch_data(batch_words, model_name=model_name)

        if not results:
            log_callback(f"Skipping batch {batch_words} (API error)")
            continue

        for data in results:
            hanzi = data.get("hanzi")
            # Fallback if Hanzi is missing from AI response (use one of the inputs if possible, but risky)
            if not hanzi:
                hanzi = batch_words[0] if len(batch_words) == 1 else "Unknown"

            log_callback(f"[DEBUG] Parsed item: {hanzi}")

            # Create Note
            note = genanki.Note(
                model=cn_model,
                fields=[
                    hanzi,
                    data.get("pinyin", ""),
                    data.get("meaning", ""),
                    data.get("examples", ""),
                ],
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
    root.geometry("650x550")

    # Theme
    sv_ttk.set_theme("dark")

    # Style configuration
    style = ttk.Style()
    style.configure("TButton", font=("Segoe UI", 11), padding=5)
    style.configure("TLabel", font=("Segoe UI", 11))
    style.configure("Header.TLabel", font=("Segoe UI", 14, "bold"))
    style.configure("Big.TEntry", font=("Segoe UI", 11), padding=5)

    # Main Container
    main_frame = ttk.Frame(root, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Header
    header_label = ttk.Label(
        main_frame, text="Chinese to Anki Generator", style="Header.TLabel"
    )
    header_label.pack(anchor=tk.W, pady=(0, 10), padx=5)

    # --- Tabs ---
    notebook = ttk.Notebook(main_frame)
    notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    # Create Tabs
    input_tab = ttk.Frame(notebook, padding="15")
    settings_tab = ttk.Frame(notebook, padding="15")
    logs_tab = ttk.Frame(notebook, padding="15")

    notebook.add(input_tab, text="  Input  ")
    notebook.add(settings_tab, text="  Settings  ")
    notebook.add(logs_tab, text="  Logs  ")

    # ==================== INPUT TAB ====================
    
    ttk.Label(
        input_tab, text="Enter Chinese words (one per line, or comma separated):"
    ).pack(anchor=tk.W, pady=(0, 5))

    # Text Input Area
    input_scroll_frame = ttk.Frame(input_tab)
    input_scroll_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
    
    word_entry = tk.Text(input_scroll_frame, height=10, font=("Arial", 14), wrap=tk.WORD, bd=0, highlightthickness=0)
    input_scrollbar = ttk.Scrollbar(input_scroll_frame, orient="vertical", command=word_entry.yview)
    word_entry["yscrollcommand"] = input_scrollbar.set
    
    input_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    word_entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    word_entry.focus()

    # Generate Button Area
    action_frame = ttk.Frame(input_tab)
    action_frame.pack(fill=tk.X)

    generate_btn = ttk.Button(
        action_frame,
        text="Generate Flashcards",
        style="Accent.TButton",
        width=25
    )
    generate_btn.pack(side=tk.RIGHT, pady=5)
    
    status_var = tk.StringVar(value="Ready")
    status_label = ttk.Label(action_frame, textvariable=status_var, font=("Segoe UI", 10, "italic"))
    status_label.pack(side=tk.LEFT, pady=5, padx=5)


    # ==================== SETTINGS TAB ====================

    # Grid config
    settings_tab.columnconfigure(1, weight=1)

    # Deck Name
    ttk.Label(settings_tab, text="Deck Name:").grid(
        row=0, column=0, sticky=tk.W, padx=(0, 10), pady=10
    )
    deck_var = tk.StringVar(value="Generated Chinese Cards")
    deck_entry = ttk.Combobox(
        settings_tab,
        textvariable=deck_var,
        values=["Generated Chinese Cards", "Most Frequent Chinese Characters"],
        font=("Segoe UI", 11),
    )
    deck_entry.grid(row=0, column=1, sticky=tk.EW, pady=10)

    # Model Selection
    ttk.Label(settings_tab, text="AI Model:").grid(
        row=1, column=0, sticky=tk.W, padx=(0, 10), pady=10
    )
    model_var = tk.StringVar(value="stepfun/step-3.5-flash:free")
    model_select = ttk.Combobox(
        settings_tab,
        textvariable=model_var,
        values=["google/gemma-3n-e2b-it:free", "arcee-ai/trinity-large-preview:free", "z-ai/glm-4.5-air:free", "stepfun/step-3.5-flash:free"],
        font=("Segoe UI", 11),
    )
    model_select.grid(row=1, column=1, sticky=tk.EW, pady=10)

    # Auto Import
    auto_import_var = tk.BooleanVar(value=True)
    auto_import_check = ttk.Checkbutton(
        settings_tab,
        text="Automatically open generated .apkg file",
        variable=auto_import_var,
    )
    auto_import_check.grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=10)

    # Separator
    ttk.Separator(settings_tab, orient="horizontal").grid(row=3, column=0, columnspan=2, sticky=tk.EW, pady=15)

    # API Key Section
    ttk.Label(settings_tab, text="OpenRouter API Key").grid(
        row=4, column=0, columnspan=2, sticky=tk.W, pady=(0, 5)
    )
    
    api_key_frame = ttk.Frame(settings_tab)
    api_key_frame.grid(row=5, column=0, columnspan=2, sticky=tk.EW)
    api_key_frame.columnconfigure(0, weight=1)
    
    api_key_var = tk.StringVar(value=os.getenv("OPENROUTER_API") or "")
    api_key_entry = ttk.Entry(
        api_key_frame, textvariable=api_key_var, font=("Segoe UI", 11), show="*"
    )
    api_key_entry.grid(row=0, column=0, sticky=tk.EW, padx=(0, 5))

    def toggle_api_visibility():
        if show_api_var.get():
            api_key_entry.config(show="")
        else:
            api_key_entry.config(show="*")

    show_api_var = tk.BooleanVar(value=False)
    show_api_check = ttk.Checkbutton(
        api_key_frame, text="Show", variable=show_api_var, command=toggle_api_visibility
    )
    show_api_check.grid(row=0, column=1, sticky=tk.W)


    # ==================== LOGS TAB ====================
    
    log_area = scrolledtext.ScrolledText(
        logs_tab, state="disabled", font=("Courier New", 11), bd=0, highlightthickness=0
    )
    log_area.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    def on_clear_log():
        log_area.config(state="normal")
        log_area.delete(1.0, tk.END)
        log_area.config(state="disabled")

    clear_btn = ttk.Button(logs_tab, text="Clear Logs", command=on_clear_log)
    clear_btn.pack(anchor=tk.E)


    # ==================== LOGIC ====================

    def log_message(message):
        # Update log area
        log_area.config(state="normal")
        log_area.insert(tk.END, message + "\n")
        log_area.see(tk.END)
        log_area.config(state="disabled")
        
        # Update simple status
        # Extract meaningful status if possible, otherwise just say "Working..."
        if "Success" in message:
            status_var.set("Generation Complete!")
        elif "Error" in message:
            status_var.set("Error Occurred")
        elif "Processing" in message:
            status_var.set("Processing...")
        else:
            # Just show the latest log line if it's short
            if len(message) < 40:
                status_var.set(message)

    def on_generate():
        # Get text from Text widget (1.0 to END-1c to avoid trailing newline)
        input_text = word_entry.get("1.0", "end-1c").strip()
        selected_model = model_var.get()
        selected_deck = deck_var.get().strip() or "Generated Chinese Cards"

        global auto_import
        auto_import = auto_import_var.get()

        if not input_text:
            messagebox.showwarning("Input Error", "Please enter at least one word.")
            return

        generate_btn.config(state=tk.DISABLED)
        word_entry.config(state=tk.DISABLED)
        
        # Switch to logs tab automatically so user sees progress? 
        # Or just show status. Let's switch to logs if it's a long process, 
        # but user might prefer staying on input. Let's stay on input but update status.
        status_var.set("Starting generation...")
        
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
                status_var.set("Error during generation")
            finally:
                root.after(0, lambda: generate_btn.config(state=tk.NORMAL))
                root.after(0, lambda: word_entry.config(state=tk.NORMAL))
                # reset status if needed or leave "Complete"

        threading.Thread(target=run_task, daemon=True).start()

    generate_btn.config(command=on_generate)
    
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
