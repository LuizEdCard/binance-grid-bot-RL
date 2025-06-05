# sentiment_analyzer.py

import json
import os
import pathlib

import onnxruntime as ort
from transformers import AutoTokenizer

from .logger import log

# Define base directories
BASE_DIR = pathlib.Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
MODELS_DIR = os.path.join(BASE_DIR, "models", "sentiment_onnx")


class SentimentAnalyzer:
    """Analyzes sentiment using a pre-trained ONNX model (llmware/slim-sentiment-onnx)."""

    def __init__(
        self, model_dir=None
    ):
        self.model_dir = model_dir if model_dir is not None else MODELS_DIR
        self.model_path = os.path.join(self.model_dir, "model.onnx")
        self.tokenizer = None
        self.session = None
        self.onnx_model_loaded = False  # Initialize status flag
        self._load_model()

    def is_available(self) -> bool:
        """Checks if the ONNX model was loaded successfully."""
        return self.onnx_model_loaded

    def _load_model(self):
        """Loads the ONNX model and tokenizer."""
        try:
            if not os.path.exists(self.model_path):
                log.info(
                    f"Sentiment analysis ONNX model not found at: {self.model_path}"
                )
                log.info("Attempting to download model automatically...")
                if not self._download_model():
                    raise FileNotFoundError(f"Failed to download model to: {self.model_path}")

            log.info(f"Loading sentiment analysis tokenizer from: {self.model_dir}")
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_dir)

            log.info(f"Loading sentiment analysis ONNX model from: {self.model_path}")
            # Consider provider options if GPU is available and configured, default is CPU
            # providers = [("CUDAExecutionProvider", {"device_id": 0}), "CPUExecutionProvider"]
            providers = ["CPUExecutionProvider"]
            self.session = ort.InferenceSession(self.model_path, providers=providers)
            self.onnx_model_loaded = True # Set flag on successful load
            log.info(
                f"Sentiment analysis model loaded successfully using {self.session.get_providers()}"
            )

        except Exception as e:
            log.error(
                f"Failed to load sentiment analysis ONNX model or tokenizer from {self.model_dir}: {e}",
                exc_info=True, # Keep exc_info for detailed traceback during first error
            )
            self.tokenizer = None
            self.session = None
            self.onnx_model_loaded = False # Ensure flag is false on failure
    
    def _download_model(self):
        """Downloads the ONNX sentiment model automatically."""
        try:
            import requests
            from huggingface_hub import hf_hub_download
            
            log.info("Starting automatic download of ONNX sentiment model...")
            
            # Create model directory
            os.makedirs(self.model_dir, exist_ok=True)
            
            # Model repository details
            repo_id = "llmware/slim-sentiment-onnx"
            
            # Download model files
            # Added .onnx_data file if it's part of the repo for larger models
            model_files = [
                "model.onnx",
                "config.json", 
                "tokenizer.json",
                "tokenizer_config.json",
                "vocab.txt",
                # Add "model.onnx_data" if applicable, though slim-sentiment-onnx might not need it.
                # Check Hugging Face repo for actual file list if issues persist.
            ]
            
            all_files_downloaded_or_exist = True
            for file_name in model_files:
                file_path = os.path.join(self.model_dir, file_name)
                if os.path.exists(file_path):
                    log.info(f"File {file_name} already exists in {self.model_dir}. Skipping download.")
                    continue

                try:
                    log.info(f"Downloading {file_name} to {self.model_dir}...")
                    hf_hub_download(
                        repo_id=repo_id,
                        filename=file_name,
                        local_dir=self.model_dir, # Download directly to the target model_dir
                        local_dir_use_symlinks=False,
                        # cache_dir=os.path.join(self.model_dir, ".cache") # Optional: use a subfolder for HF cache
                    )
                    log.info(f"Downloaded {file_name} successfully to {self.model_dir}")
                except Exception as e:
                    # If a specific file (like .onnx_data) is optional, this might not be critical
                    # For core files like model.onnx or tokenizer, it is.
                    if file_name in ["model.onnx", "config.json", "tokenizer.json", "vocab.txt"]:
                        log.error(f"Critical file {file_name} failed to download: {e}", exc_info=True)
                        all_files_downloaded_or_exist = False
                        break # Stop if a critical file fails
                    else:
                        log.warning(f"Optional file {file_name} not found or failed to download: {e}")
            
            if not all_files_downloaded_or_exist:
                log.error(f"One or more critical ONNX model files failed to download to {self.model_dir}.")
                return False

            # Verify model.onnx was downloaded specifically
            if os.path.exists(self.model_path):
                log.info(f"ONNX sentiment model files appear to be present in {self.model_dir}.")
                return True
            else:
                log.error(f"Core model file model.onnx not found in {self.model_dir} after download attempt.")
                return False
                
        except ImportError:
            log.error("Required library 'huggingface_hub' missing for model download. Please install: pip install huggingface_hub", exc_info=True)
            return False
        except Exception as e:
            log.error(f"An unexpected error occurred during ONNX model download process: {e}", exc_info=True)
            return False

    def analyze(self, text: str) -> dict | None:
        """Analyzes the sentiment of the input text.

        Args:
            text: The text to analyze.

        Returns:
            A dictionary containing the sentiment (e.g., {"sentiment": "positive"})
            or None if analysis fails.
        """
        if not self.session or not self.tokenizer:
            log.error(
                "Sentiment analyzer model or tokenizer not loaded. Cannot analyze."
            )
            return None

        try:
            # Tokenize the input text
            inputs = self.tokenizer(
                text, return_tensors="np", padding=True, truncation=True, max_length=512
            )

            # Prepare inputs for ONNX Runtime
            # The input names might vary depending on the model conversion. Check the model structure if needed.
            # Common names are 'input_ids', 'attention_mask'.
            ort_inputs = {
                self.session.get_inputs()[0].name: inputs["input_ids"],
                self.session.get_inputs()[1].name: inputs["attention_mask"],
            }

            # Run inference
            ort_outputs = self.session.run(None, ort_inputs)

            # Process the output
            # The output format depends on how the model was trained/converted.
            # For slim-sentiment-onnx, it's expected to be logits or directly interpretable output.
            # We need to decode the output tokens back to text/json.
            # Assuming the output logits need decoding (this might need
            # adjustment based on model specifics)
            output_ids = ort_outputs[0]
            decoded_output = self.tokenizer.decode(
                output_ids[0], skip_special_tokens=True
            )

            # The model card says it generates a python dictionary.
            # Let's try to parse the decoded output as JSON (often models
            # output JSON strings).
            try:
                # Clean potential artifacts if needed
                cleaned_output = decoded_output.strip()
                # Find the start and end of the dictionary
                start_index = cleaned_output.find("{")
                end_index = cleaned_output.rfind("}")
                if start_index != -1 and end_index != -1:
                    dict_str = cleaned_output[start_index : end_index + 1]
                    sentiment_result = json.loads(dict_str)
                    log.debug(
                        f"Sentiment analysis result for '{text[:50]}...': {sentiment_result}"
                    )
                    return sentiment_result
                else:
                    log.warning(
                        f"Could not find valid dictionary in model output: {cleaned_output}"
                    )
                    return None
            except json.JSONDecodeError as json_err:
                log.error(
                    f"Failed to parse sentiment model output as JSON: {decoded_output}. Error: {json_err}"
                )
                return None
            except Exception as parse_err:
                log.error(
                    f"Error processing sentiment model output: {decoded_output}. Error: {parse_err}"
                )
                return None

        except Exception as e:
            log.error(
                f"Error during sentiment analysis for text '{text[:50]}...': {e}",
                exc_info=True,
            )
            return None


# Example Usage (for testing)
if __name__ == "__main__":
    # Ensure logger is configured for standalone testing
    import logging

    logging.basicConfig(level=logging.INFO)
    log.setLevel(logging.INFO)

    analyzer = SentimentAnalyzer()

    if analyzer.session:
        test_text_positive = "This is great news! The market is booming today."
        test_text_negative = "I am very concerned about the recent downturn."
        test_text_neutral = "The report was released this morning."

        sentiment_pos = analyzer.analyze(test_text_positive)
        print(f"Sentiment (Positive Test): {sentiment_pos}")

        sentiment_neg = analyzer.analyze(test_text_negative)
        print(f"Sentiment (Negative Test): {sentiment_neg}")

        sentiment_neu = analyzer.analyze(test_text_neutral)
        print(f"Sentiment (Neutral Test): {sentiment_neu}")
    else:
        print("Sentiment Analyzer could not be initialized.")
