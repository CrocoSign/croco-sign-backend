from deepl import DeepLClient

from croco_sign.domain.models import SpokenTranslationInput
from croco_sign.domain.models import Language

_convert_langauge_to_model_label = {
    Language.POLISH: "PL",
    Language.ENGLISH: None, 
}

class DeeplSpokenLanguageTranslator:
    def __init__(self, auth_key: str) -> None:
        self.client = DeepLClient(auth_key=auth_key)
        
    def translate(self, input: SpokenTranslationInput) -> str:
        if input.target_language == Language.ENGLISH:
            return input.text
        
        target_lang = _convert_langauge_to_model_label[input.target_language]
        
        output = self.client.translate_text(
                    input.text,
                    source_lang="EN",
                    target_lang=target_lang
                )
        
        return output.text
        
if __name__ == "__main__":
    translator = DeeplSpokenLanguageTranslator()
    output = translator.translate(SpokenTranslationInput(
        target_language="pl",
        text="Hello, how are you?",
    ))
    
    print(output)
    
