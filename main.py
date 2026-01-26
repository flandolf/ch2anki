import subprocess
import sys
import os
import tempfile
import json
import threading
import re
import platform
import logging
from typing import List, Dict, Optional, Any
import genanki
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import sv_ttk
# from g4f.client import ClientFactory # Lazy imported to avoid XCB errors

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Config:
    """Configuration constants for the application."""
    MODEL_ID = 1607392319
    DECK_ID = 2059400110
    DECK_NAME = 'Generated Chinese Cards'
    
    CSS = """
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

    TEMPLATE = {
      'name': 'Card 1',
      'qfmt': '<div class="hanzi">{{Hanzi}}</div>',
      'afmt': '''{{FrontSide}}
                 <hr id="answer">
                 <div class="pinyin">{{Pinyin}}</div>
                 <div class="meaning">{{Meaning}}</div>
                 <div class="examples">{{Examples}}</div>''',
    }

    BATCH_SIZE = 3

class ChineseCardGenerator:
    """Handles the generation of Anki cards from Chinese words."""
    
    def __init__(self, model_name: str = "openai-fast"):
        self.model_name = model_name
        # Lazy import to avoid startup XCB errors
        from g4f.client import ClientFactory
        self.client = ClientFactory.create_client("pollinations")
        self.model = self._create_anki_model()

    def _create_anki_model(self) -> genanki.Model:
        return genanki.Model(
            Config.MODEL_ID,
            'Chinese Vocab Model',
            fields=[
                {'name': 'Hanzi'},
                {'name': 'Pinyin'},
                {'name': 'Meaning'},
                {'name': 'Examples'},
            ],
            templates=[Config.TEMPLATE],
            css=Config.CSS
        )

    def _fetch_data(self, words: List[str]) -> List[Dict[str, Any]]:
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
            logger.info(f"Sending batch prompt for: {words_str} using model: {self.model_name}")
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                web_search=False
            )
            content = response.choices[0].message.content.strip()
            logger.debug(f"Raw content received: {content}")
            
            # Clean up markdown if present
            content = self._clean_json_string(content)
                
            parsed_data = json.loads(content)
            
            # Ensure it's a list
            if isinstance(parsed_data, dict):
                return [parsed_data]
            return parsed_data
            
        except Exception as e:
            logger.error(f"Error fetching data from AI: {e}")
            return []

    def _clean_json_string(self, content: str) -> str:
        """Removes markdown code blocks from a string."""
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]
        
        if content.endswith("```"):
            content = content[:-3]
        
        return content.strip()

    def generate_package(self, input_text: str, log_callback=print, auto_open: bool = True) -> Optional[str]:
        """Generates an Anki package (.apkg) for the given word(s)."""
        words = [w.strip() for w in re.split(r'[,，\n]', input_text) if w.strip()]
        
        if not words:
            log_callback("No valid words found.")
            return None

        deck = genanki.Deck(Config.DECK_ID, Config.DECK_NAME)
        count = 0
        
        for i in range(0, len(words), Config.BATCH_SIZE):
            batch_words = words[i:i + Config.BATCH_SIZE]
            log_callback(f"Processing batch: {', '.join(batch_words)}...")
            
            results = self._fetch_data(batch_words)
            
            if not results:
                log_callback(f"Skipping batch {batch_words} (API error)")
                continue

            for data in results:
                hanzi = data.get('hanzi')
                if not hanzi:
                    hanzi = batch_words[0] if len(batch_words) == 1 else "Unknown"

                log_callback(f"Parsed item: {hanzi}")

                note = genanki.Note(
                  model=self.model,
                  fields=[
                      hanzi, 
                      str(data.get('pinyin', '')), 
                      str(data.get('meaning', '')), 
                      str(data.get('examples', ''))
                  ]
                )
                deck.add_note(note)
                count += 1

        if count == 0:
            log_callback("No cards generated.")
            return None

        filepath = self._save_deck(deck, words, count)
        log_callback(f"Success! Saved {count} cards to: {filepath}")
        
        if auto_open:
            self._open_file(filepath)
            
        return filepath

    def _save_deck(self, deck: genanki.Deck, words: List[str], count: int) -> str:
        safe_name = re.sub(r'[\\/*?:"<>|]', "", words[0])
        filename = f"{safe_name}.apkg" if count == 1 else f"{safe_name}_batch_{count}.apkg"
        filepath = os.path.join(tempfile.gettempdir(), filename)
        genanki.Package(deck).write_to_file(filepath)
        return filepath

    def _open_file(self, filepath: str):
        current_os = platform.system()
        try:
            if current_os == "Darwin":  # macOS
                subprocess.call(["open", filepath])
            else:  # Linux
                subprocess.call(["xdg-open", filepath])
        except Exception as e:
            logger.error(f"Failed to open file: {e}")

class App:
    """GUI Application for Chinese to Anki Generator."""
    
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Chinese to Anki Generator")
        self.root.geometry("600x500")
        
        self.generator = None  # Initialized when needed or immediately if model fixed
        
        self._setup_ui()
        sv_ttk.set_theme("dark")

    def _setup_ui(self):
        # Styles
        style = ttk.Style()
        style.configure("TButton", font=("Arial", 12))
        style.configure("TLabel", font=("Arial", 12))

        # Main Frame
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Input Section
        ttk.Label(main_frame, text="Enter Chinese Word(s):").pack(anchor=tk.W, pady=(0, 5))
        self.word_entry = ttk.Entry(main_frame, font=("Arial", 14))
        self.word_entry.pack(fill=tk.X, pady=(0, 10))
        self.word_entry.focus()

        # Model Selection
        model_frame = ttk.Frame(main_frame)
        model_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(model_frame, text="Select Model:").pack(side=tk.LEFT, padx=(0, 10))
        self.model_var = tk.StringVar(value="gemini")
        self.model_select = ttk.Combobox(model_frame, textvariable=self.model_var, values=["gemini", "openai-fast"], state="readonly")
        self.model_select.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Generate Button
        self.generate_btn = ttk.Button(main_frame, text="Generate Flashcard", command=self.on_generate)
        self.generate_btn.pack(fill=tk.X, pady=10)

        # Log Area
        ttk.Label(main_frame, text="Status Log:").pack(anchor=tk.W, pady=(5, 0))
        self.log_area = scrolledtext.ScrolledText(main_frame, height=12, state='disabled', font=("Courier", 11))
        self.log_area.pack(fill=tk.BOTH, expand=True)

        # Clear Button
        ttk.Button(main_frame, text="Clear Log", command=self.clear_log).pack(fill=tk.X, pady=(10,0))

        # Bind Enter key
        self.root.bind('<Return>', lambda event: self.on_generate())

    def log_message(self, message: str):
        self.root.after(0, self._log_message_main, message)
        # Also log to console (logging is thread-safe)
        logger.info(message)

    def _log_message_main(self, message: str):
        self.log_area.config(state='normal')
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)
        self.log_area.config(state='disabled')

    def clear_log(self):
        self.log_area.config(state='normal')
        self.log_area.delete(1.0, tk.END)
        self.log_area.config(state='disabled')

    def on_generate(self):
        word = self.word_entry.get().strip()
        selected_model = self.model_var.get()
        
        if not word:
            messagebox.showwarning("Input Error", "Please enter a word.")
            return

        self._toggle_inputs(False)
        self.log_message("-" * 30)
        
        # Initialize generator with selected model
        self.generator = ChineseCardGenerator(model_name=selected_model)

        threading.Thread(target=self._run_generation_task, args=(word,), daemon=True).start()

    def _run_generation_task(self, word: str):
        try:
            self.generator.generate_package(word, log_callback=self.log_message)
        except Exception as e:
            self.log_message(f"Critical Error: {e}")
            logger.exception("Task failed")
        finally:
            self.root.after(0, lambda: self._toggle_inputs(True))

    def _toggle_inputs(self, enable: bool):
        state = tk.NORMAL if enable else tk.DISABLED
        self.generate_btn.config(state=state)
        self.word_entry.config(state=state)
        self.model_select.config(state=state)

def main():
    if len(sys.argv) > 1 and sys.argv[1] != "--gui":
        # CLI Mode
        input_word = sys.argv[1]
        model = "gemini" # Default CLI model
        generator = ChineseCardGenerator(model_name=model)
        generator.generate_package(input_word)
    else:
        # GUI Mode
        root = tk.Tk()
        app = App(root)
        root.mainloop()

if __name__ == "__main__":
    main()

