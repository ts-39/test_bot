
class AudioProcessor extends AudioWorkletProcessor {
    constructor(options) {
        super();
        
        this.frameSize = options.processorOptions?.frameSize || 320; // 20ms at 16kHz
        this.buffer = new Float32Array(this.frameSize);
        this.bufferIndex = 0;
        
        console.log('AudioProcessor initialized with frame size:', this.frameSize);
    }
    
    process(inputs, outputs, parameters) {
        const input = inputs[0];
        const output = outputs[0];
        
        if (input.length > 0) {
            const inputChannel = input[0]; // Mono channel
            const outputChannel = output[0];
            
            if (outputChannel) {
                outputChannel.set(inputChannel);
            }
            
            for (let i = 0; i < inputChannel.length; i++) {
                this.buffer[this.bufferIndex] = inputChannel[i];
                this.bufferIndex++;
                
                if (this.bufferIndex >= this.frameSize) {
                    this.sendAudioFrame();
                    this.bufferIndex = 0;
                }
            }
        }
        
        return true; // Keep processor alive
    }
    
    sendAudioFrame() {
        const frameData = new Float32Array(this.buffer);
        
        this.port.postMessage({
            type: 'audioData',
            data: frameData
        });
    }
}

registerProcessor('audio-processor', AudioProcessor);
