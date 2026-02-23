import subprocess
import sys
import os
import tempfile
import json
import genanki
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import re
import platform
import sv_ttk
import requests

def get_config_dir():
    app_name = "ch2anki"
    system = platform.system()
    if system == "Darwin":
        return os.path.expanduser(f"~/Library/Application Support/{app_name}")
    elif system == "Windows":
        return os.path.join(os.environ.get('APPDATA', os.path.expanduser("~")), app_name)
    else:
        return os.path.expanduser(f"~/.config/{app_name}")

CONFIG_FILE = os.path.join(get_config_dir(), "config.json")
print(f"Config path: {CONFIG_FILE}")

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                c = json.load(f)
                print(f"Loaded config: {c.keys()}")
                return c
        except Exception as e:
            print(f"Error loading config: {e}", file=sys.stderr)
            return {}
    return {}

def save_config(config):
    try:
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
        print("Config saved successfully.")
    except Exception as e:
        print(f"Error saving config: {e}", file=sys.stderr)

# Load Initial Configuration
initial_config = load_config()
auto_import = initial_config.get("auto_import", True)

# Anki Model Configuration
# Unique IDs (generated randomly, keep consistent for deck updates)
MODEL_ID = 1607392319
CHEM_MODEL_ID = 1607392320
VCE_MODEL_ID = 1607392321
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

chem_style = """
.card {
 font-family: arial;
 font-size: 20px;
 text-align: center;
 color: black;
 background-color: white;
}
.concept { font-size: 30px; font-weight: bold; color: #FF7070; }
.symbol { font-size: 24px; color: #555; font-family: monospace; }
.definition { font-size: 20px; font-style: italic; }
.examples { text-align: left; margin-top: 20px; font-size: 16px; }
"""

vce_style = """
.card {
 font-family: 'Times New Roman', serif;
 font-size: 18px;
 text-align: left;
 color: #333;
 background-color: #fdf6e3;
 padding: 20px;
}
.term { font-size: 24px; font-weight: bold; color: #268bd2; border-bottom: 2px solid #b58900; padding-bottom: 10px; margin-bottom: 15px; }
.subsystem { font-size: 14px; font-style: italic; color: #859900; margin-bottom: 5px; text-transform: uppercase; letter-spacing: 1px;}
.definition { font-size: 18px; line-height: 1.6; margin-bottom: 15px; }
.example { font-size: 16px; color: #657b83; background-color: #eee8d5; padding: 10px; border-left: 4px solid #cb4b16; font-style: italic; }
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

chem_model = genanki.Model(
    CHEM_MODEL_ID,
    "Chemistry Model",
    fields=[
        {"name": "Concept"},
        {"name": "Symbol"},
        {"name": "Definition"},
        {"name": "Examples"},
    ],
    templates=[
        {
            "name": "Card 1",
            "qfmt": '<div class="concept">{{Concept}}</div>',
            "afmt": """{{FrontSide}}
                 <hr id="answer">
                 <div class="symbol">{{Symbol}}</div>
                 <div class="definition">{{Definition}}</div>
                 <div class="examples">{{Examples}}</div>""",
        },
    ],
    css=chem_style,
)

eng_lang_model = genanki.Model(
    VCE_MODEL_ID,
    "VCE English Language Model",
    fields=[
        {"name": "Term"},
        {"name": "Subsystem"},
        {"name": "Definition"},
        {"name": "Example"},
    ],
    templates=[
        {
            "name": "Linguistics Card",
            "qfmt": '<div class="term">{{Term}}</div>',
            "afmt": """{{FrontSide}}
                 <hr id="answer">
                 <div class="subsystem">{{Subsystem}}</div>
                 <div class="definition">{{Definition}}</div>
                 <div class="example">{{Example}}</div>""",
        },
    ],
    css=vce_style,
)


def get_batch_data(words: list, model_name: str = "openai-fast", api_key: str = "", mode: str = "Chinese"):
    """Fetch structured data for a list of words using g4f."""
    words_str = ", ".join(words)
    
    if mode == "Chemistry":
        prompt = f"""
        You are a Chemistry tutor. Create flashcards for the following concepts/elements/molecules: {words_str}.
        
        RESPONSE FORMAT INSTRUCTIONS:
        You must output a valid JSON ARRAY only. Do not wrap the output in markdown code blocks.
        The output must be a list of objects, one for each input.
        
        Each object must have exactly these keys:
        - "concept": The input concept/element/molecule/compound name.
        - "symbol": The chemical symbol, formula, or structure description (e.g. H2O, O, NaCl).
        - "definition": Concise definition or description.
        - "examples": HTML string with exactly 2 examples or facts formatted EXACTLY like this: "<b>Fact 1:</b> CONTENT<br><br><b>Fact 2:</b> CONTENT".

        CONTENT INSTRUCTIONS:
        - Ensure scientific accuracy.
        - If the input is an element, include atomic number in the definition.
        """
    elif mode == "English Language (VCE)":
        prompt = f"""
        You are a VCE English Language tutor. Create definitions/metalanguage flashcards for the following terms/concepts: {words_str}.
        
        RESPONSE FORMAT INSTRUCTIONS:
        You must output a valid JSON ARRAY only. Do not wrap the output in markdown code blocks.
        The output must be a list of objects, one for each input.
        
        Each object must have exactly these keys:
        - "term": The linguistic term or concept (e.g. 'Standard Australian English', 'Isogloss', 'Sociolect').
        - "subsystem": The relevant subsystem (e.g. Phonology, Lexicology) or category (e.g. Language Change, Social Purpose).
        - "definition": A precise, VCE-standard definition using appropriate metalanguage.
        - "example": A clear example of the term in use, or a case study reference.

        CONTENT INSTRUCTIONS:
        - Ensure subsystem classification is accurate.
        - Definitions should be concise but complete.
        """
    else:
        # Default to Chinese
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

    # Resolve API Key
    if not api_key:
        # Try environment variable fallback or config
        api_key = os.getenv('OPENROUTER_API') or load_config().get("api_key") or ""

    if not api_key:
        print("[ERROR] No API Key provided. Please set OPENROUTER_API env var or configure in GUI.", file=sys.stderr)
        return None
    try:
        print(
            f"[DEBUG] Sending batch prompt for: {words_str} using model: {model_name}"
        )
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
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



def get_data_from_notes(notes_text: str, model_name: str, api_key: str, mode: str):
    """Fetch structured data from unstructured notes."""
    
    if mode == "Chemistry":
        prompt = f"""
        You are a Chemistry tutor. Analyze the following notes and extract key concepts into flashcards.
        
        NOTES:
        {notes_text}
        
        RESPONSE FORMAT INSTRUCTIONS:
        You must output a valid JSON ARRAY only. Do not wrap the output in markdown code blocks.
        The output must be a list of objects.
        
        Each object must have exactly these keys:
        - "concept": The concept/element/molecule name.
        - "symbol": The chemical symbol, formula, or structure description.
        - "definition": Concise definition or description based on the notes.
        - "examples": HTML string with exactly 2 examples/facts: "<b>Fact 1:</b> ...<br><br><b>Fact 2:</b> ...".
        """
    elif mode == "English Language (VCE)":
        prompt = f"""
        You are a VCE English Language tutor. Analyze the following text/notes and extract key linguistic terms, metalanguage, or concepts into flashcards.
        
        TEXT:
        {notes_text}
        
        RESPONSE FORMAT INSTRUCTIONS:
        You must output a valid JSON ARRAY only. Do not wrap the output in markdown code blocks.
        The output must be a list of objects.
        
        Each object must have exactly these keys:
        - "term": The linguistic feature or concept found in the notes.
        - "subsystem": The linguistic subsystem (e.g. Syntax, Semantics, Discourse).
        - "definition": Definition or explanation of the concept based on the notes.
        - "example": An example from the notes or a standard example if one isn't provided.

        CONTENT INSTRUCTIONS:
        - Focus on accurate metalanguage.
        - Ensure examples are relevant to the Australian context if applicable (e.g. ethnolects).
        """
    else:
        # Default or Chinese mode, but for notes "Chinese" mode might mean "Extract Chinese vocab from text"
        # Or it might mean "Turn these English notes into Chinese flashcards"?
        # Let's assume for now "Notes" tab uses the active mode to determine the OUTPUT format.
        # If Mode is Chinese, maybe we are extracting vocab from a Chinese text?
        prompt = f"""
        You are a Chinese language tutor. Analyze the following text and extract key Chinese vocabulary words into flashcards.
        
        TEXT:
        {notes_text}
        
        RESPONSE FORMAT INSTRUCTIONS:
        You must output a valid JSON ARRAY only. Do not wrap the output in markdown code blocks.
        The output must be a list of objects.
        
        Each object must have exactly these keys:
        - "hanzi": The extracted Chinese word.
        - "pinyin": The pinyin with tone marks.
        - "meaning": Concise English definition.
        - "examples": HTML string with exactly 2 examples: "<b>Example 1:</b> HANZI<br>(PINYIN)<br>ENGLISH<br><br><b>Example 2:</b> ...".
        """

    # Resolve API Key
    if not api_key:
        api_key = os.getenv('OPENROUTER_API') or load_config().get("api_key") or ""

    if not api_key:
        print("[ERROR] No API Key provided.", file=sys.stderr)
        return None

    try:
        print(f"[DEBUG] Sending notes prompt len={len(notes_text)} using {model_name}")
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            data=json.dumps({
                "model": model_name,
                "messages": [{"role": "user", "content": prompt}],
            }),
        )
        response_data = response.json()
        content = response_data["choices"][0]["message"]["content"]
        
        # Clean up markdown
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        
        return json.loads(content.strip())
    except Exception as e:
        print(f"Error fetching data from AI: {e}", file=sys.stderr)
        return None

def create_anki_package_from_notes(
    notes_text: str,
    log_callback=print,
    model_name: str = "stepfun/step-3.5-flash:free",
    deck_name: str = "Generated Notes Cards",
    api_key: str = "",
    mode: str = "Chinese"
):
    """Generates an Anki package from unstructured notes."""
    if not notes_text.strip():
        log_callback("No notes provided.")
        return

    log_callback(f"Processing notes ({len(notes_text)} chars) using {model_name} (Mode: {mode})...")
    
    # Simple chunking if text is too long (approx 4000 chars per chunk to be safe with context limits)
    # This is a naive split, ideally we'd split by paragraphs.
    CHUNK_SIZE = 4000
    chunks = [notes_text[i:i+CHUNK_SIZE] for i in range(0, len(notes_text), CHUNK_SIZE)]
    
    deck = genanki.Deck(DECK_ID, deck_name)
    count = 0
    all_results = []

    for i, chunk in enumerate(chunks):
        log_callback(f"Processing chunk {i+1}/{len(chunks)}...")
        results = get_data_from_notes(chunk, model_name, api_key, mode)
        
        if not results:
            log_callback(f"Failed to extract info from chunk {i+1}")
            continue
            
        all_results.extend(results)

    for data in all_results:
        try:
            if mode == "Chemistry":
                concept = data.get("concept", "Unknown")
                log_callback(f"[DEBUG] Parsed item: {concept}")
                note = genanki.Note(
                    model=chem_model,
                    fields=[
                        concept,
                        data.get("symbol", ""),
                        data.get("definition", ""),
                        data.get("examples", ""),
                    ],
                )
                deck.add_note(note)
            elif mode == "English Language (VCE)":
                term = data.get("term", "Term")
                log_callback(f"[DEBUG] Parsed item: {term}...")
                note = genanki.Note(
                    model=eng_lang_model,
                    fields=[
                        term,
                        data.get("subsystem", ""),
                        data.get("definition", ""),
                        data.get("example", ""),
                    ],
                )
                deck.add_note(note)
            else:
                hanzi = data.get("hanzi", "Unknown")
                log_callback(f"[DEBUG] Parsed item: {hanzi}")
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
        except Exception as e:
            log_callback(f"Error creating note: {e}")

    if count == 0:
        log_callback("No cards generated.")
        return

    filename = f"notes_export_{count}.apkg"
    filepath = os.path.join(tempfile.gettempdir(), filename)
    genanki.Package(deck).write_to_file(filepath)
    
    log_callback(f"Success! Saved {count} cards to: {filepath}")
    
    if auto_import:
        current_os = platform.system()
        if current_os == "Darwin":
            subprocess.call(["open", filepath])
        else:
            subprocess.call(["xdg-open", filepath])

def create_anki_package(
    input_text: str,
    log_callback=print,
    model_name: str = "stepfun/step-3.5-flash:free",
    deck_name: str = "Generated Chinese Cards",
    api_key: str = "",
    mode: str = "Chinese"
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
            f"Processing batch: {', '.join(batch_words)} using {model_name} (Mode: {mode})..."
        )

        results = get_batch_data(batch_words, model_name=model_name, api_key=api_key, mode=mode)

        if not results:
            log_callback(f"Skipping batch {batch_words} (API error)")
            continue

        for data in results:
            if mode == "Chemistry":
                concept = data.get("concept")
                if not concept:
                    concept = batch_words[0] if len(batch_words) == 1 else "Unknown"
                
                log_callback(f"[DEBUG] Parsed item: {concept}")
                
                note = genanki.Note(
                    model=chem_model,
                    fields=[
                        concept,
                        data.get("symbol", ""),
                        data.get("definition", ""),
                        data.get("examples", ""),
                    ],
                )
                deck.add_note(note)
            elif mode == "English Language (VCE)":
                term = data.get("term") or "Linguistic Term"
                
                log_callback(f"[DEBUG] Parsed item: {term}...")
                
                note = genanki.Note(
                    model=eng_lang_model,
                    fields=[
                        term,
                        data.get("subsystem", ""),
                        data.get("definition", ""),
                        data.get("example", ""),
                    ],
                )
                deck.add_note(note)
            else:
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
    root = tk.Tk()
    root.title("Anki Generator")
    root.geometry("650x550")

    # Load persistent config
    config = load_config()

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
        main_frame, text="Anki Generator", style="Header.TLabel"
    )
    header_label.pack(anchor=tk.W, pady=(0, 10), padx=5)

    # --- Tabs ---
    notebook = ttk.Notebook(main_frame)
    notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    # Create Tabs
    input_tab = ttk.Frame(notebook, padding="15")
    notes_tab = ttk.Frame(notebook, padding="15")
    settings_tab = ttk.Frame(notebook, padding="15")
    logs_tab = ttk.Frame(notebook, padding="15")

    notebook.add(input_tab, text="  Input  ")
    notebook.add(notes_tab, text="  Notes  ")
    notebook.add(settings_tab, text="  Settings  ")
    notebook.add(logs_tab, text="  Logs  ")

    # Shared Status Var
    status_var = tk.StringVar(value="Ready")

    # ==================== INPUT TAB ====================
    
    ttk.Label(
        input_tab, text="Enter terms (one per line, or comma separated):"
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
    
    status_label = ttk.Label(action_frame, textvariable=status_var, font=("Segoe UI", 10, "italic"))
    status_label.pack(side=tk.LEFT, pady=5, padx=5)

    # ==================== NOTES TAB ====================
    
    ttk.Label(
        notes_tab, text="Enter unstructured notes (AI will extract flashcards):"
    ).pack(anchor=tk.W, pady=(0, 5))

    # Notes Input Area
    notes_scroll_frame = ttk.Frame(notes_tab)
    notes_scroll_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
    
    notes_entry = tk.Text(notes_scroll_frame, height=10, font=("Arial", 12), wrap=tk.WORD, bd=0, highlightthickness=0)
    notes_scrollbar = ttk.Scrollbar(notes_scroll_frame, orient="vertical", command=notes_entry.yview)
    notes_entry["yscrollcommand"] = notes_scrollbar.set
    
    notes_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    notes_entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    # Generate Button Area (Notes)
    notes_action_frame = ttk.Frame(notes_tab)
    notes_action_frame.pack(fill=tk.X)

    generate_notes_btn = ttk.Button(
        notes_action_frame,
        text="Generate from Notes",
        style="Accent.TButton",
        width=25
    )
    generate_notes_btn.pack(side=tk.RIGHT, pady=5)
    
    notes_status_label = ttk.Label(notes_action_frame, textvariable=status_var, font=("Segoe UI", 10, "italic"))
    notes_status_label.pack(side=tk.LEFT, pady=5, padx=5)



    # ==================== SETTINGS TAB ====================

    # Grid config
    settings_tab.columnconfigure(1, weight=1)

    # Mode Selection
    ttk.Label(settings_tab, text="Mode:").grid(
        row=0, column=0, sticky=tk.W, padx=(0, 10), pady=10
    )
    mode_var = tk.StringVar(value=config.get("mode", "Chinese"))
    mode_select = ttk.Combobox(
        settings_tab,
        textvariable=mode_var,
        values=["Chinese", "Chemistry", "English Language (VCE)"],
        font=("Segoe UI", 11),
        state="readonly",
    )
    mode_select.grid(row=0, column=1, sticky=tk.EW, pady=10)

    # Deck Name
    ttk.Label(settings_tab, text="Deck Name:").grid(
        row=1, column=0, sticky=tk.W, padx=(0, 10), pady=10
    )
    deck_var = tk.StringVar(value=config.get("deck_name", "Generated Chinese Cards"))
    deck_entry = ttk.Combobox(
        settings_tab,
        textvariable=deck_var,
        values=["Generated Chinese Cards", "Most Frequent Chinese Characters", "Chemistry Deck", "VCE EngLang Deck"],
        font=("Segoe UI", 11),
    )
    deck_entry.grid(row=1, column=1, sticky=tk.EW, pady=10)

    # Model Selection
    ttk.Label(settings_tab, text="AI Model:").grid(
        row=2, column=0, sticky=tk.W, padx=(0, 10), pady=10
    )
    model_var = tk.StringVar(value=config.get("model", "stepfun/step-3.5-flash:free"))
    model_select = ttk.Combobox(
        settings_tab,
        textvariable=model_var,
        values=["google/gemma-3n-e2b-it:free", "arcee-ai/trinity-large-preview:free", "z-ai/glm-4.5-air:free", "stepfun/step-3.5-flash:free"],
        font=("Segoe UI", 11),
    )
    model_select.grid(row=2, column=1, sticky=tk.EW, pady=10)

    # Auto Import
    auto_import_var = tk.BooleanVar(value=config.get("auto_import", True))
    auto_import_check = ttk.Checkbutton(
        settings_tab,
        text="Automatically open generated .apkg file",
        variable=auto_import_var,
    )
    auto_import_check.grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=10)

    # Separator
    ttk.Separator(settings_tab, orient="horizontal").grid(row=4, column=0, columnspan=2, sticky=tk.EW, pady=15)

    # API Key Section
    ttk.Label(settings_tab, text="OpenRouter API Key").grid(
        row=5, column=0, columnspan=2, sticky=tk.W, pady=(0, 5)
    )
    
    api_key_frame = ttk.Frame(settings_tab)
    api_key_frame.grid(row=6, column=0, columnspan=2, sticky=tk.EW)
    api_key_frame.columnconfigure(0, weight=1)
    
    api_key_val = config.get("api_key")
    if not api_key_val:
        api_key_val = os.getenv("OPENROUTER_API") or ""
    
    api_key_var = tk.StringVar(value=api_key_val)
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


    def save_current_settings(event=None):
        settings = {
            "mode": mode_var.get(),
            "deck_name": deck_var.get().strip(),
            "model": model_var.get(),
            "auto_import": auto_import_var.get(),
            "api_key": api_key_var.get().strip()
        }
        save_config(settings)
        # Optional: visual feedback in status bar?
        try:
             # Only update status if it's not currently running a generation task
             if "Processing" not in status_var.get() and "Starting" not in status_var.get():
                 status_var.set("Settings saved")
        except Exception:
            pass

    def on_close():
        save_current_settings()
        root.destroy()
    
    # Bind settings changes to save automatically
    mode_select.bind("<<ComboboxSelected>>", save_current_settings)
    deck_entry.bind("<<ComboboxSelected>>", save_current_settings)
    deck_entry.bind("<FocusOut>", save_current_settings)
    model_select.bind("<<ComboboxSelected>>", save_current_settings)
    model_select.bind("<FocusOut>", save_current_settings)
    auto_import_check.config(command=save_current_settings)
    api_key_entry.bind("<FocusOut>", save_current_settings)
    api_key_entry.bind("<Return>", save_current_settings)
    api_key_entry.bind("<KeyRelease>", lambda event: save_current_settings())

    root.protocol("WM_DELETE_WINDOW", on_close)

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
        current_api_key = api_key_var.get().strip()
        selected_mode = mode_var.get()

        global auto_import
        auto_import = auto_import_var.get()

        if not input_text:
            messagebox.showwarning("Input Error", "Please enter at least one word.")
            return

        # Save settings explicitly before running
        save_current_settings()

        generate_btn.config(state=tk.DISABLED)
        word_entry.config(state=tk.DISABLED)
        
        # Switch to logs tab automatically so user sees progress? 
        # Or just show status. Let's switch to logs if it's a long process, 
        # but user might prefer staying on input. Let's stay on input but update status.
        status_var.set("Starting generation...")
        
        log_message("\n" + "=" * 40)
        log_message(f"Starting generation task ({selected_mode})...")

        def run_task():
            try:
                create_anki_package(
                    input_text,
                    log_callback=log_message,
                    model_name=selected_model,
                    deck_name=selected_deck,
                    api_key=current_api_key,
                    mode=selected_mode
                )
            except Exception as e:
                log_message(f"Error: {e}")
                status_var.set("Error during generation")
            finally:
                root.after(0, lambda: generate_btn.config(state=tk.NORMAL))
                root.after(0, lambda: word_entry.config(state=tk.NORMAL))
                # reset status if needed or leave "Complete"

        threading.Thread(target=run_task, daemon=True).start()

    def on_generate_notes():
        input_text = notes_entry.get("1.0", "end-1c").strip()
        selected_model = model_var.get()
        selected_deck = deck_var.get().strip() or "Generated Notes Cards"
        current_api_key = api_key_var.get().strip()
        selected_mode = mode_var.get()

        global auto_import
        auto_import = auto_import_var.get()

        if not input_text:
            messagebox.showwarning("Input Error", "Please enter some notes.")
            return

        # Save settings
        save_current_settings()

        generate_notes_btn.config(state=tk.DISABLED)
        notes_entry.config(state=tk.DISABLED)
        
        status_var.set("Starting notes generation...")
        log_message("\n" + "=" * 40)
        log_message(f"Starting notes processing ({selected_mode})...")

        def run_notes_task():
            try:
                create_anki_package_from_notes(
                    input_text,
                    log_callback=log_message,
                    model_name=selected_model,
                    deck_name=selected_deck,
                    api_key=current_api_key,
                    mode=selected_mode
                )
            except Exception as e:
                log_message(f"Error: {e}")
                status_var.set("Error during generation")
            finally:
                root.after(0, lambda: generate_notes_btn.config(state=tk.NORMAL))
                root.after(0, lambda: notes_entry.config(state=tk.NORMAL))

        threading.Thread(target=run_notes_task, daemon=True).start()

    generate_btn.config(command=on_generate)
    generate_notes_btn.config(command=on_generate_notes)
    
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
