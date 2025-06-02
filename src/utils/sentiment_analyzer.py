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
        self._load_model()

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
            log.info(
                f"Sentiment analysis model loaded successfully using {self.session.get_providers()}"
            )

        except Exception as e:
            log.error(
                f"Failed to load sentiment analysis model or tokenizer: {e}",
                exc_info=True,
            )
            self.tokenizer = None
            self.session = None
    
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
            model_files = [
                "model.onnx",
                "config.json", 
                "tokenizer.json",
                "tokenizer_config.json",
                "vocab.txt"
            ]
            
            for file_name in model_files:
                try:
                    log.info(f"Downloading {file_name}...")
                    downloaded_path = hf_hub_download(
                        repo_id=repo_id,
                        filename=file_name,
                        cache_dir=self.model_dir,
                        local_dir=self.model_dir,
                        local_dir_use_symlinks=False
                    )
                    log.info(f"Downloaded {file_name} successfully")
                except Exception as e:
                    log.warning(f"Failed to download {file_name}: {e}")
                    # Continue with other files
            
            # Verify model.onnx was downloaded
            if os.path.exists(self.model_path):
                log.info("ONNX sentiment model downloaded successfully!")
                return True
            else:
                log.error("Model download failed - model.onnx not found")
                return False
                
        except ImportError as e:
            log.error(f"Required libraries missing for model download: {e}")
            log.error("Please install: pip install huggingface_hub")
            return False
        except Exception as e:
            log.error(f"Failed to download ONNX model: {e}")
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
