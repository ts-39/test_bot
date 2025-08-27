import asyncio
import json
import logging
import os
import struct
from typing import Dict, Any, Optional
import websockets
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv
import uvicorn

from pipecat_pipeline import PipecatPipeline
from audio_processor import AudioProcessor

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Google Meet Voice Bot Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.pipelines: Dict[str, PipecatPipeline] = {}
        self.audio_processors: Dict[str, AudioProcessor] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        
        self.pipelines[client_id] = PipecatPipeline(client_id)
        self.audio_processors[client_id] = AudioProcessor()
        
        logger.info(f"Client {client_id} connected")

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        if client_id in self.pipelines:
            self.pipelines[client_id].cleanup()
            del self.pipelines[client_id]
        if client_id in self.audio_processors:
            del self.audio_processors[client_id]
        logger.info(f"Client {client_id} disconnected")

    async def send_audio(self, client_id: str, audio_data: bytes):
        if client_id in self.active_connections:
            try:
                await self.active_connections[client_id].send_bytes(audio_data)
            except Exception as e:
                logger.error(f"Error sending audio to {client_id}: {e}")

    async def send_message(self, client_id: str, message: dict):
        if client_id in self.active_connections:
            try:
                await self.active_connections[client_id].send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error sending message to {client_id}: {e}")

manager = ConnectionManager()

@app.get("/")
async def root():
    return {"message": "Google Meet Voice Bot Server", "status": "running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": asyncio.get_event_loop().time()}

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(websocket, client_id)
    
    try:
        while True:
            try:
                message = await websocket.receive()
                
                if "bytes" in message:
                    audio_data = message["bytes"]
                    await handle_audio_input(client_id, audio_data)
                    
                elif "text" in message:
                    control_data = json.loads(message["text"])
                    await handle_control_message(client_id, control_data)
                    
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error handling message from {client_id}: {e}")
                await manager.send_message(client_id, {
                    "type": "error",
                    "message": str(e)
                })
                
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(client_id)

async def handle_audio_input(client_id: str, audio_data: bytes):
    """Process incoming audio data through Pipecat pipeline"""
    try:
        if client_id not in manager.pipelines:
            logger.error(f"No pipeline found for client {client_id}")
            return
            
        pipeline = manager.pipelines[client_id]
        audio_processor = manager.audio_processors[client_id]
        
        if len(audio_data) % 2 != 0:
            logger.warning(f"Invalid audio data length: {len(audio_data)}")
            return
            
        audio_samples = audio_processor.bytes_to_samples(audio_data)
        
        response_audio = await pipeline.process_audio(audio_samples)
        
        if response_audio is not None:
            response_bytes = audio_processor.samples_to_bytes(response_audio)
            await manager.send_audio(client_id, response_bytes)
            
    except Exception as e:
        logger.error(f"Error processing audio for {client_id}: {e}")
        await manager.send_message(client_id, {
            "type": "error",
            "message": f"Audio processing error: {str(e)}"
        })

async def handle_control_message(client_id: str, control_data: dict):
    """Handle control messages from client"""
    try:
        message_type = control_data.get("type")
        
        if message_type == "ready":
            await manager.send_message(client_id, {
                "type": "ready_ack",
                "message": "Server ready for audio processing"
            })
            
        elif message_type == "ping":
            await manager.send_message(client_id, {
                "type": "pong",
                "timestamp": asyncio.get_event_loop().time()
            })
            
        elif message_type == "configure":
            config = control_data.get("config", {})
            if client_id in manager.pipelines:
                await manager.pipelines[client_id].update_config(config)
                await manager.send_message(client_id, {
                    "type": "config_updated",
                    "message": "Pipeline configuration updated"
                })
                
        elif message_type == "meta":
            metadata = control_data.get("data", {})
            logger.info(f"Received metadata from {client_id}: {metadata}")
            
        else:
            logger.warning(f"Unknown control message type: {message_type}")
            
    except Exception as e:
        logger.error(f"Error handling control message from {client_id}: {e}")
        await manager.send_message(client_id, {
            "type": "error",
            "message": f"Control message error: {str(e)}"
        })

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    
    logger.info(f"Starting server on {host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")
