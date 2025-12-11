"""
Minimax API Client for TTS Generation
"""

import os
import aiohttp
import asyncio
import logging
import subprocess
import tempfile
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class MinimaxAPI:
    """Minimax API Client"""
    
    def __init__(self):
        self.group_id = os.getenv("MINIMAX_GROUP_ID")
        self.api_key = os.getenv("MINIMAX_API_KEY")
        self.base_url = "https://api.minimaxi.chat"
        
        if not self.group_id or not self.api_key:
            logger.error("❌ Minimax credentials not set!")
            raise ValueError("MINIMAX_GROUP_ID and MINIMAX_API_KEY are required")
    
    async def generate_tts(self, text: str, voice_id: str, **kwargs) -> Dict[str, Any]:
        """
        Generate TTS audio
        
        Args:
            text: Text to convert
            voice_id: Voice ID
            **kwargs: Additional parameters
            
        Returns:
            Dictionary with audio data
        """
        try:
            # Prepare request
            payload = {
                "model": kwargs.get('model', 'speech-2.6-turbo'),
                "text": text,
                "output_format": "url",
                "voice_setting": {
                    "voice_id": voice_id,
                    "speed": kwargs.get('speed', 0.9),
                    "vol": kwargs.get('volume', 1.6),
                    "pitch": kwargs.get('pitch', 0)
                }
            }
            
            # Add emotion if specified
            emotion = kwargs.get('emotion', 'auto')
            if emotion != 'auto':
                payload['voice_setting']['emotion'] = emotion
            
            # Make API request
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/v1/t2a_v2?GroupId={self.group_id}"
                
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                
                async with session.post(url, json=payload, headers=headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Minimax API error: {error_text}")
                        return {
                            'success': False,
                            'error': f'API Error: {response.status}'
                        }
                    
                    data = await response.json()
                    
                    if data.get('base_resp', {}).get('status_code') != 0:
                        error_msg = data.get('base_resp', {}).get('status_msg', 'Unknown error')
                        return {
                            'success': False,
                            'error': f'Minimax Error: {error_msg}'
                        }
                    
                    mp3_url = data.get('data', {}).get('audio')
                    if not mp3_url:
                        return {
                            'success': False,
                            'error': 'No audio URL in response'
                        }
                    
                    # Download and convert MP3 to OGG
                    audio_data = await self._download_and_convert(mp3_url)
                    
                    if not audio_data:
                        return {
                            'success': False,
                            'error': 'Failed to process audio'
                        }
                    
                    return {
                        'success': True,
                        'audio_data': audio_data,
                        'format': 'ogg',
                        'codec': 'libopus',
                        'sample_rate': 48000,
                        'channels': 1
                    }
                    
        except asyncio.TimeoutError:
            return {
                'success': False,
                'error': 'API timeout'
            }
        except Exception as e:
            logger.error(f"TTS generation error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _download_and_convert(self, mp3_url: str) -> Optional[bytes]:
        """Download MP3 and convert to OGG/Opus"""
        try:
            # Download MP3
            async with aiohttp.ClientSession() as session:
                async with session.get(mp3_url) as response:
                    if response.status != 200:
                        logger.error(f"Failed to download audio: {response.status}")
                        return None
                    
                    mp3_data = await response.read()
            
            # Convert to OGG/Opus using FFmpeg
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as mp3_file:
                mp3_file.write(mp3_data)
                mp3_path = mp3_file.name
            
            ogg_path = mp3_path.replace('.mp3', '.ogg')
            
            # FFmpeg command for OGG/Opus conversion
            ffmpeg_cmd = [
                'ffmpeg',
                '-i', mp3_path,
                '-c:a', 'libopus',
                '-ar', '48000',
                '-ac', '1',
                '-b:a', '64k',
                '-vbr', 'on',
                '-compression_level', '10',
                '-application', 'audio',
                '-frame_duration', '20',
                '-f', 'ogg',
                ogg_path
            ]
            
            # Run FFmpeg
            process = await asyncio.create_subprocess_exec(
                *ffmpeg_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                logger.error(f"FFmpeg error: {stderr.decode()}")
                return None
            
            # Read converted file
            with open(ogg_path, 'rb') as f:
                ogg_data = f.read()
            
            # Cleanup
            import os
            os.unlink(mp3_path)
            os.unlink(ogg_path)
            
            return ogg_data
            
        except Exception as e:
            logger.error(f"Audio conversion error: {e}")
            return None
        finally:
            # Ensure cleanup
            import os
            for path in [mp3_path, ogg_path]:
                if os.path.exists(path):
                    try:
                        os.unlink(path)
                    except:
                        pass
    
    async def get_available_voices(self) -> list:
        """Get available voices from Minimax"""
        # Note: This is a placeholder. Minimax may not have a public voices API.
        # You might need to hardcode available voices or implement differently.
        return [
            {
                "name": "Moss Audio (Turbo)",
                "voice_id": "moss_audio_4d4208c8-b67d-11f0-afaf-868268514f62",
                "model": "speech-2.6-turbo",
                "language": "en",
                "gender": "male"
            }
        ]