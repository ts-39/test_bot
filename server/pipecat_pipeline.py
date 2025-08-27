import asyncio
import logging
import os
from typing import Optional, Dict, Any
import numpy as np
from dotenv import load_dotenv

try:
    import openai
    from deepgram import DeepgramClient, PrerecordedOptions, LiveOptions
    import anthropic
except ImportError as e:
    logging.error(f"Failed to import AI service SDKs: {e}")
    logging.error("Please install required packages: pip install openai deepgram-sdk anthropic")
    raise

load_dotenv()
logger = logging.getLogger(__name__)

class PipecatPipeline:
    """Custom pipeline for STT -> LLM -> TTS processing"""
    
    def __init__(self, client_id: str):
        self.client_id = client_id
        self.stt_client = None
        self.llm_client = None
        self.tts_client = None
        self.mock_mode = False
        
        self.config = self._load_default_config()
        
        asyncio.create_task(self._initialize_services())
        
    def _load_default_config(self) -> Dict[str, Any]:
        """Load default configuration from environment variables"""
        return {
            "stt": {
                "provider": os.getenv("STT_PROVIDER", "deepgram"),
                "api_key": os.getenv("DEEPGRAM_API_KEY"),
                "model": os.getenv("STT_MODEL", "nova-2"),
                "language": os.getenv("STT_LANGUAGE", "ja"),
            },
            "llm": {
                "provider": os.getenv("LLM_PROVIDER", "openai"),
                "api_key": os.getenv("OPENAI_API_KEY"),
                "model": os.getenv("LLM_MODEL", "gpt-4"),
                "temperature": float(os.getenv("LLM_TEMPERATURE", "0.7")),
            },
            "tts": {
                "provider": os.getenv("TTS_PROVIDER", "cartesia"),
                "api_key": os.getenv("CARTESIA_API_KEY"),
                "voice_id": os.getenv("TTS_VOICE_ID", "a0e99841-438c-4a64-b679-ae501e7d6091"),
                "model": os.getenv("TTS_MODEL", "sonic-english"),
            },
            "persona": {
                "system_prompt": self._load_system_prompt(),
                "language": os.getenv("PERSONA_LANGUAGE", "ja"),
                "tone": os.getenv("PERSONA_TONE", "friendly"),
            }
        }
    
    def _load_system_prompt(self) -> str:
        """Load system prompt from config file or environment"""
        try:
            with open("../configs/persona.md", "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return os.getenv("SYSTEM_PROMPT", 
                "あなたは親しみやすいAIアシスタントです。Google Meetの会議参加者と自然な会話を行ってください。")
    
    async def _initialize_services(self):
        """Initialize AI services with configured providers"""
        try:
            missing_keys = []
            
            if self.config["stt"]["provider"] == "deepgram" and not self.config["stt"]["api_key"]:
                missing_keys.append("DEEPGRAM_API_KEY")
            
            if self.config["llm"]["provider"] == "openai" and not self.config["llm"]["api_key"]:
                missing_keys.append("OPENAI_API_KEY")
            elif self.config["llm"]["provider"] == "anthropic" and not self.config["llm"]["api_key"]:
                missing_keys.append("ANTHROPIC_API_KEY")
            
            if missing_keys:
                logger.warning(f"Missing API keys for client {self.client_id}: {missing_keys}")
                logger.warning("Services will run in mock mode for testing")
                self.stt_client = None
                self.llm_client = None
                self.tts_client = None
                self.mock_mode = True
            else:
                self.stt_client = self._create_stt_service()
                self.llm_client = self._create_llm_service()
                self.tts_client = None  # Will implement TTS later
                self.mock_mode = False
            
            self.conversation_history = [
                {
                    "role": "system",
                    "content": self.config["persona"]["system_prompt"]
                }
            ]
            
            mode_str = "mock mode" if self.mock_mode else "full AI services"
            logger.info(f"Services initialized for client {self.client_id} in {mode_str}")
            
        except Exception as e:
            logger.error(f"Failed to initialize services for {self.client_id}: {e}")
            self.mock_mode = True
            self.stt_client = None
            self.llm_client = None
            self.tts_client = None
            logger.warning(f"Falling back to mock mode for client {self.client_id}")
    
    def _create_stt_service(self):
        """Create STT service based on configuration"""
        provider = self.config["stt"]["provider"]
        
        if provider == "deepgram":
            return DeepgramClient(self.config["stt"]["api_key"])
        else:
            raise ValueError(f"Unsupported STT provider: {provider}")
    
    def _create_llm_service(self):
        """Create LLM service based on configuration"""
        provider = self.config["llm"]["provider"]
        
        if provider == "openai":
            return openai.OpenAI(api_key=self.config["llm"]["api_key"])
        elif provider == "anthropic":
            return anthropic.Anthropic(api_key=self.config["llm"]["api_key"])
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")
    
    def _create_tts_service(self):
        """Create TTS service based on configuration"""
        provider = self.config["tts"]["provider"]
        
        logger.info(f"TTS provider {provider} configured but not yet implemented")
        return None
    
    async def process_audio(self, audio_samples: np.ndarray) -> Optional[np.ndarray]:
        """Process audio through the custom pipeline"""
        try:
            if self.mock_mode:
                logger.info(f"Mock mode: simulating audio processing for client {self.client_id}")
                
                silence_duration = 1.0  # 1 second of silence
                sample_rate = 16000
                silence_samples = np.zeros(int(silence_duration * sample_rate), dtype=np.int16)
                
                return silence_samples
            
            if not self.stt_client or not self.llm_client:
                logger.error(f"Services not initialized for client {self.client_id}")
                return None
            
            transcript = await self._transcribe_audio(audio_samples)
            if not transcript or not transcript.strip():
                return None
            
            logger.info(f"Transcribed: {transcript}")
            
            response_text = await self._generate_response(transcript)
            if not response_text:
                return None
            
            logger.info(f"LLM Response: {response_text}")
            
            silence_duration = 2.0  # 2 seconds of silence
            sample_rate = 16000
            silence_samples = np.zeros(int(silence_duration * sample_rate), dtype=np.int16)
            
            return silence_samples
            
        except Exception as e:
            logger.error(f"Error processing audio for {self.client_id}: {e}")
            return None
    
    async def _transcribe_audio(self, audio_samples: np.ndarray) -> Optional[str]:
        """Transcribe audio using configured STT service"""
        try:
            audio_bytes = audio_samples.tobytes()
            
            options = PrerecordedOptions(
                model=self.config["stt"]["model"],
                language=self.config["stt"]["language"],
                smart_format=True,
                punctuate=True,
            )
            
            import io
            audio_buffer = io.BytesIO(audio_bytes)
            
            response = self.stt_client.listen.prerecorded.v("1").transcribe_file(
                {"buffer": audio_buffer, "mimetype": "audio/wav"},
                options
            )
            
            if response.results and response.results.channels:
                alternatives = response.results.channels[0].alternatives
                if alternatives and alternatives[0].transcript:
                    return alternatives[0].transcript.strip()
            
            return None
            
        except Exception as e:
            logger.error(f"STT error for {self.client_id}: {e}")
            return None
    
    async def _generate_response(self, user_input: str) -> Optional[str]:
        """Generate response using configured LLM"""
        try:
            self.conversation_history.append({
                "role": "user",
                "content": user_input
            })
            
            provider = self.config["llm"]["provider"]
            
            if provider == "openai":
                response = await self.llm_client.chat.completions.create(
                    model=self.config["llm"]["model"],
                    messages=self.conversation_history,
                    temperature=self.config["llm"]["temperature"],
                    max_tokens=150
                )
                
                assistant_message = response.choices[0].message.content
                
            elif provider == "anthropic":
                system_message = self.conversation_history[0]["content"]
                messages = self.conversation_history[1:]  # Skip system message
                
                response = await self.llm_client.messages.create(
                    model=self.config["llm"]["model"],
                    system=system_message,
                    messages=messages,
                    temperature=self.config["llm"]["temperature"],
                    max_tokens=150
                )
                
                assistant_message = response.content[0].text
            
            else:
                raise ValueError(f"Unsupported LLM provider: {provider}")
            
            self.conversation_history.append({
                "role": "assistant",
                "content": assistant_message
            })
            
            if len(self.conversation_history) > 20:
                self.conversation_history = [self.conversation_history[0]] + self.conversation_history[-18:]
            
            return assistant_message
            
        except Exception as e:
            logger.error(f"LLM error for {self.client_id}: {e}")
            return None
    
    async def update_config(self, new_config: Dict[str, Any]):
        """Update service configuration"""
        try:
            self.config.update(new_config)
            
            await self._initialize_services()
            
            logger.info(f"Configuration updated for client {self.client_id}")
            
        except Exception as e:
            logger.error(f"Error updating config for {self.client_id}: {e}")
            raise
    
    def cleanup(self):
        """Clean up service resources"""
        try:
            self.stt_client = None
            self.llm_client = None
            self.tts_client = None
            
            logger.info(f"Services cleaned up for client {self.client_id}")
            
        except Exception as e:
            logger.error(f"Error cleaning up services for {self.client_id}: {e}")
