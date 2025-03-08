import sys
import os
from PyQt6 import QtWidgets, QtCore, QtGui
import pygame.mixer
import rtmidi
import numpy as np
from scipy.io import wavfile
from scipy import signal

class WavInstrumentApp(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("WAV MIDI Instrument")
        self.setGeometry(100, 100, 800, 600)

        # Initialize audio with specific settings
        pygame.mixer.pre_init(44100, -16, 2, 512)
        pygame.mixer.init()
        pygame.mixer.set_num_channels(128)
        
        self.base_sample = None
        self.processed_sounds = {}
        self.active_notes = {}
        
        # GUI Setup
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        layout = QtWidgets.QVBoxLayout(central_widget)

        # Debug Section
        debug_group = QtWidgets.QGroupBox("Debug Information")
        debug_layout = QtWidgets.QVBoxLayout()
        
        self.debug_label = QtWidgets.QLabel("Debug info:")
        debug_layout.addWidget(self.debug_label)
        
        self.midi_debug = QtWidgets.QLabel("MIDI status: Not connected")
        debug_layout.addWidget(self.midi_debug)
        
        self.sample_debug = QtWidgets.QLabel("Sample status: No sample loaded")
        debug_layout.addWidget(self.sample_debug)
        
        self.note_debug = QtWidgets.QLabel("Last MIDI event: None")
        debug_layout.addWidget(self.note_debug)
        
        debug_group.setLayout(debug_layout)
        layout.addWidget(debug_group)

        # MIDI Setup
        port_group = QtWidgets.QGroupBox("MIDI Settings")
        port_layout = QtWidgets.QVBoxLayout()
        
        self.midi_port_selector = QtWidgets.QComboBox()
        port_layout.addWidget(QtWidgets.QLabel("MIDI Input Port:"))
        port_layout.addWidget(self.midi_port_selector)
        
        self.refresh_ports_button = QtWidgets.QPushButton("Refresh MIDI Ports")
        self.refresh_ports_button.clicked.connect(self.get_available_midi_ports)
        port_layout.addWidget(self.refresh_ports_button)
        
        port_group.setLayout(port_layout)
        layout.addWidget(port_group)

        # Sample Loader Section
        sample_group = QtWidgets.QGroupBox("Sample Settings")
        sample_layout = QtWidgets.QVBoxLayout()

        self.load_button = QtWidgets.QPushButton("Load WAV Sample")
        self.load_button.clicked.connect(self.load_sample)
        sample_layout.addWidget(self.load_button)

        self.base_note = QtWidgets.QSpinBox()
        self.base_note.setRange(0, 127)
        self.base_note.setValue(60)
        self.base_note.setPrefix("Base Note (MIDI): ")
        sample_layout.addWidget(self.base_note)

        range_layout = QtWidgets.QHBoxLayout()
        self.min_note = QtWidgets.QSpinBox()
        self.min_note.setRange(0, 127)
        self.min_note.setValue(36)
        self.min_note.setPrefix("Min Note: ")
        range_layout.addWidget(self.min_note)

        self.max_note = QtWidgets.QSpinBox()
        self.max_note.setRange(0, 127)
        self.max_note.setValue(84)
        self.max_note.setPrefix("Max Note: ")
        range_layout.addWidget(self.max_note)
        
        sample_layout.addLayout(range_layout)

        self.process_button = QtWidgets.QPushButton("Process Sample")
        self.process_button.clicked.connect(self.process_sample)
        sample_layout.addWidget(self.process_button)

        sample_group.setLayout(sample_layout)
        layout.addWidget(sample_group)

        # Volume Control
        volume_group = QtWidgets.QGroupBox("Volume Control")
        volume_layout = QtWidgets.QVBoxLayout()
        
        self.volume_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.volume_slider.setMinimum(0)
        self.volume_slider.setMaximum(100)
        self.volume_slider.setValue(80)
        self.volume_slider.valueChanged.connect(self.update_volume)
        volume_layout.addWidget(QtWidgets.QLabel("Master Volume:"))
        volume_layout.addWidget(self.volume_slider)
        
        volume_group.setLayout(volume_layout)
        layout.addWidget(volume_group)

        self.progress = QtWidgets.QProgressBar()
        layout.addWidget(self.progress)

        self.test_sound_button = QtWidgets.QPushButton("Test Sound (Middle C)")
        self.test_sound_button.clicked.connect(self.test_sound)
        layout.addWidget(self.test_sound_button)

        # Initialize MIDI
        self.midi_in = None
        self.get_available_midi_ports()
        self.midi_port_selector.currentIndexChanged.connect(self.select_midi_input)

    def test_sound(self):
        note = 60  # Middle C
        if note in self.processed_sounds:
            sound = self.processed_sounds[note]
            sound.play()
            self.debug_label.setText(f"Playing test sound for note {note}")
        else:
            self.debug_label.setText(f"No processed sound for note {note}")

    def get_available_midi_ports(self):
        self.midi_port_selector.clear()
        midi_in = rtmidi.MidiIn()
        ports = midi_in.get_ports()
        
        if not ports:
            self.midi_debug.setText("No MIDI input ports found")
            return
            
        self.midi_port_selector.addItems(ports)
        self.midi_debug.setText(f"Available MIDI ports: {', '.join(ports)}")

    def select_midi_input(self):
        if self.midi_in:
            self.midi_in.close_port()

        try:
            self.midi_in = rtmidi.MidiIn()
            port_name = self.midi_port_selector.currentText()
            port_index = self.midi_port_selector.currentIndex()
            self.midi_in.open_port(port_index)
            self.midi_in.set_callback(self.midi_callback)
            self.midi_debug.setText(f"Connected to MIDI port: {port_name}")
        except Exception as e:
            self.midi_debug.setText(f"Error opening MIDI port: {str(e)}")

    def load_sample(self):
        file_name, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Load WAV Sample", "", "WAV Files (*.wav);;All Files (*)"
        )
        if file_name:
            try:
                sample_rate, audio_data = wavfile.read(file_name)
                if len(audio_data.shape) > 1:
                    audio_data = np.mean(audio_data, axis=1)

                audio_data = audio_data.astype(np.float32)
                audio_data /= np.max(np.abs(audio_data))

                self.base_sample = {
                    'path': file_name,
                    'rate': sample_rate,
                    'data': audio_data
                }
                
                self.sample_debug.setText(f"Loaded sample: {os.path.basename(file_name)}\n"
                                          f"Sample rate: {sample_rate}Hz\n"
                                          f"Length: {len(audio_data)} samples")
            except Exception as e:
                self.sample_debug.setText(f"Error loading sample: {str(e)}")

    def process_sample(self):
        if not self.base_sample:
            self.sample_debug.setText("Please load a sample first")
            return

        try:
            self.processed_sounds.clear()
            base_freq = 440 * (2 ** ((self.base_note.value() - 69) / 12))
            total_notes = self.max_note.value() - self.min_note.value() + 1
            self.progress.setMaximum(total_notes)
            self.progress.setValue(0)

            for note in range(self.min_note.value(), self.max_note.value() + 1):
                target_freq = 440 * (2 ** ((note - 69) / 12))
                pitch_ratio = target_freq / base_freq
                
                original_length = len(self.base_sample['data'])
                new_length = int(original_length / pitch_ratio)
                
                resampled = signal.resample(self.base_sample['data'], new_length)
                audio_int16 = np.int16(resampled * 32767)
                
                try:
                    sound = pygame.mixer.Sound(audio_int16)
                    self.processed_sounds[note] = sound
                except Exception as e:
                    self.sample_debug.setText(f"Error creating sound for note {note}: {str(e)}")
                    continue

                self.progress.setValue(note - self.min_note.value() + 1)
                QtWidgets.QApplication.processEvents()

            self.sample_debug.setText(f"Processed {len(self.processed_sounds)} notes\n"
                                      f"Range: {self.min_note.value()} to {self.max_note.value()}")
        except Exception as e:
            self.sample_debug.setText(f"Error processing sample: {str(e)}")

    def update_volume(self):
        master_volume = self.volume_slider.value() / 100.0
        for sound in self.processed_sounds.values():
            sound.set_volume(master_volume)

    def midi_callback(self, message, time_stamp=None):
        if not message or len(message[0]) < 3:
            return

        status = message[0][0]
        note = message[0][1]
        velocity = message[0][2]
        channel = status & 0x0F  # Extract channel number

        self.note_debug.setText(f"MIDI event: status={hex(status)}, channel={channel}, note={note}, velocity={velocity}")

        # Note On (0x90 to 0x9F) or Note On for channel 9 (0x98)
        if (0x90 <= status <= 0x9F or status == 0x98) and velocity > 0:
            self.play_note(note, velocity)
        # Note Off (0x80 to 0x8F) or Note On with velocity = 0 (0x90 with velocity = 0)
        elif (0x80 <= status <= 0x8F or (status == 0x98 and velocity == 0)):
            self.stop_note(note)

    def play_note(self, note, velocity):
        if note in self.processed_sounds:
            try:
                volume = (velocity / 127) * (self.volume_slider.value() / 100)
                channel = pygame.mixer.find_channel()
                if channel:
                    sound = self.processed_sounds[note]
                    sound.set_volume(volume)
                    channel.play(sound)
                    self.active_notes[note] = channel
                    self.note_debug.setText(f"Playing note: {note} (velocity: {velocity})")
                else:
                    self.note_debug.setText("No free channels available")
            except Exception as e:
                self.note_debug.setText(f"Error playing note {note}: {str(e)}")
        else:
            self.note_debug.setText(f"No sound processed for note {note}")

    def stop_note(self, note):
        if note in self.active_notes:
            try:
                channel = self.active_notes[note]
                channel.stop()
                del self.active_notes[note]
                self.note_debug.setText(f"Stopped note: {note}")
            except Exception as e:
                self.note_debug.setText(f"Error stopping note {note}: {str(e)}")

    def closeEvent(self, event):
        if self.midi_in:
            self.midi_in.close_port()
        pygame.mixer.quit()
        event.accept()

def main():
    app = QtWidgets.QApplication(sys.argv)
    window = WavInstrumentApp()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
