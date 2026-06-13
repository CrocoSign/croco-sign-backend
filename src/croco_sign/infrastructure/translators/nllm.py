from __future__ import annotations

import threading

from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

from croco_sign.domain.models import SpokenTranslationInput
from croco_sign.domain.models import Language

_MODEL_NAME = "facebook/nllb-200-distilled-1.3B"

_convert_langauge_to_model_label = {
    Language.POLISH: "pol_Latn",
    Language.ENGLISH: "eng_Latn", 
}

class NLLMSpokenLanguageTranslator:
    """Implements the SpokenLanguageTranslator port over Meta's NLLB model."""

    def __init__(self) -> None:
        self.model = AutoModelForSeq2SeqLM.from_pretrained(_MODEL_NAME)
        self.tokenizer = AutoTokenizer.from_pretrained(_MODEL_NAME)
        self._tok_lock = threading.Lock()

    def translate(self, input: SpokenTranslationInput) -> str:
        if input.target_language == Language.ENGLISH:
            return input.text
        
        target_language = _convert_langauge_to_model_label[input.target_language]
        
        # Encoding touches shared, mutable tokenizer state -> serialize it.
        with self._tok_lock:
            inputs = self.tokenizer(input.text, return_tensors="pt").to(self.model.device)
            forced_bos_token_id = self.tokenizer.convert_tokens_to_ids(
                tokens=target_language
            )

        # Inference reads the immutable shared weights only -> safe to run in
        # parallel across threads, so no lock here.
        translated_tokens = self.model.generate(
            **inputs,
            forced_bos_token_id=forced_bos_token_id,
            max_length=30,
        )

        with self._tok_lock:
            return self.tokenizer.batch_decode(
                translated_tokens, skip_special_tokens=True
            )[0]


if __name__ == "__main__":
    translator = NLLMSpokenLanguageTranslator()
    output = translator.translate(
        SpokenTranslationInput(
            target_language="pl",
            text="Hello, it is nice to see you!",
        )
    )

    print(output)
