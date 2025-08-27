import numpy as np
import struct
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class AudioProcessor:
    """Audio processing utilities for PCM 16kHz/16bit/mono format"""
    
    def __init__(self):
        self.sample_rate = 16000
        self.sample_width = 2  # 16-bit = 2 bytes
        self.channels = 1      # mono
        self.frame_duration_ms = 20  # 20ms frames
        self.samples_per_frame = int(self.sample_rate * self.frame_duration_ms / 1000)  # 320 samples
        
    def bytes_to_samples(self, audio_bytes: bytes) -> np.ndarray:
        """Convert PCM bytes to numpy array of samples"""
        try:
            samples = struct.unpack(f'<{len(audio_bytes)//2}h', audio_bytes)
            return np.array(samples, dtype=np.int16)
        except Exception as e:
            logger.error(f"Error converting bytes to samples: {e}")
            return np.array([], dtype=np.int16)
    
    def samples_to_bytes(self, samples: np.ndarray) -> bytes:
        """Convert numpy array of samples to PCM bytes"""
        try:
            if samples.dtype != np.int16:
                samples = samples.astype(np.int16)
            
            return struct.pack(f'<{len(samples)}h', *samples)
        except Exception as e:
            logger.error(f"Error converting samples to bytes: {e}")
            return b''
    
    def validate_frame_size(self, audio_bytes: bytes) -> bool:
        """Validate that audio frame is the expected size (20ms = 320 samples = 640 bytes)"""
        expected_bytes = self.samples_per_frame * self.sample_width
        return len(audio_bytes) == expected_bytes
    
    def pad_or_trim_frame(self, audio_bytes: bytes) -> bytes:
        """Pad or trim audio frame to expected size"""
        expected_bytes = self.samples_per_frame * self.sample_width
        
        if len(audio_bytes) == expected_bytes:
            return audio_bytes
        elif len(audio_bytes) < expected_bytes:
            padding = b'\x00' * (expected_bytes - len(audio_bytes))
            return audio_bytes + padding
        else:
            return audio_bytes[:expected_bytes]
    
    def apply_gain(self, samples: np.ndarray, gain_db: float) -> np.ndarray:
        """Apply gain to audio samples"""
        try:
            if gain_db == 0:
                return samples
            
            gain_linear = 10 ** (gain_db / 20)
            
            gained_samples = samples * gain_linear
            return np.clip(gained_samples, -32768, 32767).astype(np.int16)
            
        except Exception as e:
            logger.error(f"Error applying gain: {e}")
            return samples
    
    def detect_silence(self, samples: np.ndarray, threshold_db: float = -40) -> bool:
        """Detect if audio frame contains mostly silence"""
        try:
            if len(samples) == 0:
                return True
            
            rms = np.sqrt(np.mean(samples.astype(np.float32) ** 2))
            
            if rms > 0:
                rms_db = 20 * np.log10(rms / 32768)  # Normalize to full scale
                return rms_db < threshold_db
            else:
                return True
                
        except Exception as e:
            logger.error(f"Error detecting silence: {e}")
            return False
    
    def mix_audio(self, samples1: np.ndarray, samples2: np.ndarray, 
                  mix_ratio: float = 0.5) -> np.ndarray:
        """Mix two audio streams together"""
        try:
            min_length = min(len(samples1), len(samples2))
            samples1 = samples1[:min_length]
            samples2 = samples2[:min_length]
            
            mixed = (samples1 * (1 - mix_ratio) + samples2 * mix_ratio)
            
            return np.clip(mixed, -32768, 32767).astype(np.int16)
            
        except Exception as e:
            logger.error(f"Error mixing audio: {e}")
            return samples1 if len(samples1) > 0 else samples2
    
    def get_audio_info(self, audio_bytes: bytes) -> dict:
        """Get information about audio data"""
        return {
            "size_bytes": len(audio_bytes),
            "duration_ms": (len(audio_bytes) // self.sample_width) / self.sample_rate * 1000,
            "sample_count": len(audio_bytes) // self.sample_width,
            "expected_frame_size": self.samples_per_frame * self.sample_width,
            "is_valid_frame": self.validate_frame_size(audio_bytes),
        }
