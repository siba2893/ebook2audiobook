# 📚 ebook2audiobook (E2A)
CPU/GPU Converter from E-Book to audiobook with chapters and metadata<br/>
using advanced TTS engines and much more.<br/>
Supports voice cloning and 1158 languages!
> [!IMPORTANT]
**This tool is intended for use with non-DRM, legally acquired eBooks only.** <br>
The authors are not responsible for any misuse of this software or any resulting legal consequences. <br>
Use this tool responsibly and in accordance with all applicable laws.

[![Discord](https://dcbadge.limes.pink/api/server/https://discord.gg/63Tv3F65k6)](https://discord.gg/63Tv3F65k6)

### Thanks to support ebook2audiobook developers!
[![Ko-Fi](https://img.shields.io/badge/Ko--fi-F16061?style=for-the-badge&logo=ko-fi&logoColor=white)](https://ko-fi.com/athomasson2) 

### Run locally

[![Quick Start](https://img.shields.io/badge/Quick%20Start-blue?style=for-the-badge)](#instructions)

[![Docker Build](https://github.com/DrewThomasson/ebook2audiobook/actions/workflows/Docker-Build.yml/badge.svg)](https://github.com/DrewThomasson/ebook2audiobook/actions/workflows/Docker-Build.yml)  [![Download](https://img.shields.io/badge/Download-Now-blue.svg)](https://github.com/DrewThomasson/ebook2audiobook/releases/latest)   


<a href="https://github.com/DrewThomasson/ebook2audiobook">
  <img src="https://img.shields.io/badge/Platform-mac%20|%20linux%20|%20windows-lightgrey" alt="Platform">
</a><a href="https://hub.docker.com/r/athomasson2/ebook2audiobook">
<img alt="Docker Pull Count" src="https://img.shields.io/docker/pulls/athomasson2/ebook2audiobook.svg"/>
</a>

### Run Remotely
[![Hugging Face](https://img.shields.io/badge/Hugging%20Face-Spaces-yellow?style=flat&logo=huggingface)](https://huggingface.co/spaces/drewThomasson/ebook2audiobook)
[![Free Google Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/DrewThomasson/ebook2audiobook/blob/main/Notebooks/colab_ebook2audiobook.ipynb) [![Kaggle](https://img.shields.io/badge/Kaggle-035a7d?style=flat&logo=kaggle&logoColor=white)](https://github.com/Rihcus/ebook2audiobookXTTS/blob/main/Notebooks/kaggle-ebook2audiobook.ipynb)

#### GUI Interface
![demo_web_gui](assets/demo_web_gui.gif)

<details>
  <summary>Click to see images of Web GUI</summary>
  <img width="1728" alt="GUI Screen 1" src="assets/gui_1.png">
  <img width="1728" alt="GUI Screen 2" src="assets/gui_2.png">
  <img width="1728" alt="GUI Screen 3" src="assets/gui_3.png">
</details>

## Demos

**New Default Voice Demo**  

https://github.com/user-attachments/assets/750035dc-e355-46f1-9286-05c1d9e88cea  

<details>
  <summary>More Demos</summary>

**ASMR Voice** 

https://github.com/user-attachments/assets/68eee9a1-6f71-4903-aacd-47397e47e422

**Rainy Day Voice**  

https://github.com/user-attachments/assets/d25034d9-c77f-43a9-8f14-0d167172b080  

**Scarlett Voice**

https://github.com/user-attachments/assets/b12009ee-ec0d-45ce-a1ef-b3a52b9f8693

**David Attenborough Voice** 

https://github.com/user-attachments/assets/81c4baad-117e-4db5-ac86-efc2b7fea921

**Example**

![Example](https://github.com/DrewThomasson/VoxNovel/blob/dc5197dff97252fa44c391dc0596902d71278a88/readme_files/example_in_app.jpeg)
</details>

## README.md

## Table of Contents
- [ebook2audiobook](#-ebook2audiobook)
- [Features](#features)
- [GUI Interface](#gui-interface)
- [Demos](#demos)
- [Supported Languages](#supported-languages)
- [Minimum Requirements](#hardware-requirements)
- [Usage](#instructions)
  - [Run Locally](#instructions)
    - [Launching Gradio Web Interface](#instructions)
    - [Basic Headless Usage](#basic-usage)
    - [Headless Custom XTTS Model Usage](#example-of-custom-model-zip-upload)
    - [Help command output](#help-command-output)
  - [Run Remotely](#run-remotely)
  - [Docker](#docker)
    - [Steps to Run](#docker)
    - [Common Docker Issues](#common-docker-issues)
  
- [Fine Tuned TTS models](#fine-tuned-tts-models)
  - [Collection of Fine-Tuned TTS Models](#fine-tuned-tts-collection)
  - [Train XTTSv2](#fine-tune-your-own-xttsv2-model)
- [Modern Web UI](#modern-web-ui)
- [Additional Engines](#additional-engines)
  - [Fish Speech 1.5](#fish-speech-15)
  - [CosyVoice 3](#cosyvoice-3)
  - [Qwen3-TTS](#qwen3-tts)
- [Performance Improvements](#performance-improvements)
- [Supported eBook Formats](#supported-ebook-formats)
- [Output Formats](#output-and-process-formats)
- [Revert to older Version](#reverting-to-older-versions)
- [Common Issues](#common-issues)
- [Special Thanks](#special-thanks)
- [Table of Contents](#table-of-contents)


## Features
- 🔧 **TTS Engines supported**: `XTTSv2`, `Bark`, `Fairseq`, `VITS`, `Tacotron2`, `Tortoise`, `GlowTTS`, `YourTTS`, `Fish Speech 1.5`, `CosyVoice 3`, `Qwen3-TTS`
- 📚 **Convert multiple file formats**: `.epub`, `.mobi`, `.azw3`, `.fb2`, `.lrf`, `.rb`, `.snb`, `.tcr`, `.pdf`, `.txt`, `.rtf`, `.doc`, `.docx`, `.html`, `.odt`, `.azw`, `.tiff`, `.tif`, `.png`, `.jpg`, `.jpeg`, `.bmp`
- 💻 **TextArea** to convert directly a short text in audio
- 🔍 **OCR scanning** for files with text pages as images
- 🔊 **High-quality text-to-speech** from near realtime to near real voice
- 🗣️ **Optional voice cloning** using your own voice file
- 🌐 **Supports 1158 languages** ([supported languages list](https://dl.fbaipublicfiles.com/mms/tts/all-tts-languages.html))
- 💻 **Low-resource friendly** — runs on **2 GB RAM / 1 GB VRAM (minimum)**
- 🎵 **Audiobook output formats**: mono or stereo `aac`, `flac`, `mp3`, `m4b`, `m4a`, `mp4`, `mov`, `ogg`, `wav`, `webm`
- 🧠 **SML tags supported** — fine-grained control of breaks, pauses, voice switching and more ([see below](#sml-tags-available))
- 🧩 **Optional custom model** using your own trained model (XTTSv2 only, other on request)
- 🎛️ **Fine-tuned preset models** trained by the E2A Team<br/>
     <i>(Contact us if you need additional fine-tuned models, or if you'd like to share yours to the official preset list)</i>
- 🌐 **Modern React/FastAPI Web UI** — full conversion flow, live SSE progress, audiobook library, and session resume ([see below](#modern-web-ui))
- ⚡ **Significantly faster GPU inference** — all 9 engines optimized for throughput on RTX 30/40-series and equivalent ([see below](#performance-improvements))
- 🐟 **Fish Speech 1.5** — new high-quality zero-shot voice cloning engine (~88–92% similarity); non-commercial use only ([CC-BY-NC-SA-4.0](https://huggingface.co/fishaudio/fish-speech-1.5))
- 🎤 **CosyVoice 3** — zero-shot voice cloning with cross-lingual and instruct mode (dialect/emotion/speed control); Apache 2.0, commercial use allowed ([FunAudioLLM/CosyVoice](https://github.com/FunAudioLLM/CosyVoice))
- 🤖 **Qwen3-TTS** — zero-shot voice cloning via Alibaba's Qwen3 transformer TTS; Apache 2.0, commercial use allowed ([QwenLM/Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS))


##  Hardware Requirements
- 2GB RAM min, 8GB recommended.
- 1GB VRAM min, 4GB recommended.
- Virtualization enabled if running on windows (Docker only).
- CPU, XPU (intel, AMD, ARM)*.
- CUDA, ROCm, JETSON
- MPS (Apple Silicon CPU)

*<i> Modern TTS engines are very slow on CPU, so use lower quality TTS like YourTTS, Tacotron2 etc..</i>

## Supported Languages
| **Arabic (ar)**    | **Chinese (zh)**    | **English (en)**   | **Spanish (es)**   |
|:------------------:|:------------------:|:------------------:|:------------------:|
| **French (fr)**    | **German (de)**     | **Italian (it)**   | **Portuguese (pt)** |
| **Polish (pl)**    | **Turkish (tr)**    | **Russian (ru)**   | **Dutch (nl)**     |
| **Czech (cs)**     | **Japanese (ja)**   | **Hindi (hi)**     | **Bengali (bn)**   |
| **Hungarian (hu)** | **Korean (ko)**     | **Vietnamese (vi)**| **Swedish (sv)**   |
| **Persian (fa)**   | **Yoruba (yo)**     | **Swahili (sw)**   | **Indonesian (id)**|
| **Slovak (sk)**    | **Croatian (hr)**   | **Tamil (ta)**     | **Danish (da)**    |
- [**+1130 languages and dialects here**](https://dl.fbaipublicfiles.com/mms/tts/all-tts-languages.html)


## Supported eBook Formats
- `.epub`, `.pdf`, `.mobi`, `.txt`, `.html`, `.rtf`, `.chm`, `.lit`,
  `.pdb`, `.fb2`, `.odt`, `.cbr`, `.cbz`, `.prc`, `.lrf`, `.pml`,
  `.snb`, `.cbc`, `.rb`, `.tcr`
- **Best results**: `.epub` or `.mobi` for automatic chapter detection

## Output and process Formats
- `.m4b`, `.m4a`, `.mp4`, `.webm`, `.mov`, `.mp3`, `.flac`, `.wav`, `.ogg`, `.aac`
- Process format can be changed in lib/conf.py

## SML tags available
- `[break]` — silence (random range **0.3–0.6 sec.**)
- `[pause]` — silence (random range **1.0–1.6 sec.**)
- `[pause:N]` — fixed pause (**N sec.**)
- `[voice:/path/to/voice/file]...[/voice]` — switch voice from default or selected voice from GUI/CLI

**Check our other repo dedicated to add SML automatically in your ebook -> [E2A-SML](https://github.com/DrewThomasson/E2A-SML)**

> [!IMPORTANT]
**Before to post an install or bug issue search carefully to the opened and closed issues TAB<br>
to be sure your issue does not exist already.**

>[!NOTE]
**EPUB format lacks any standard structure like what is a chapter, paragraph, preface etc.<br>
So you should first remove manually any text you don't want to be converted in audio.**


### Instructions 
1. **Clone repo**
	```bash
	git clone https://github.com/DrewThomasson/ebook2audiobook.git
	cd ebook2audiobook
	```

2. **Install / Run ebook2audiobook**:

   - **Linux/MacOS**  
     ```bash
     ./ebook2audiobook.command
     ```
     <i>Note for MacOS users: homebrew is installed to install missing programs.</i>
     
   - **Mac Launcher**  
     Double click `Mac Ebook2Audiobook Launcher.command`


   - **Windows**  
     ```bash
     ebook2audiobook.cmd
     ```
     or
     Double click `ebook2audiobook.cmd`

     <i>Note for Windows users: scoop is installed to install missing programs without administrator privileges.</i>
   
1. **Open the Web App**: Click the URL provided in the terminal to access the web app and convert eBooks. `http://localhost:7860/`
2. **For Public Link**:
   `./ebook2audiobook.command --share` (Linux/MacOS)
   `ebook2audiobook.cmd --share` (Windows)
   `python app.py --share` (all OS)

> [!IMPORTANT]
**If the script is stopped and run again, you need to refresh your gradio GUI interface<br>
to let the web page reconnect to the new connection socket.**

### Basic  Usage
   - **Linux/MacOS**:
     ```bash
     ./ebook2audiobook.command --headless --ebook <path_to_ebook_file> --voice <path_to_voice_file> --language <language_code>
     ```
   - **Windows**
     ```bash
     ebook2audiobook.cmd --headless --ebook <path_to_ebook_file> --voice <path_to_voice_file> --language <language_code>
     ```
     
  - **[--ebook]**: Path to your eBook file
  - **[--voice]**: Voice cloning file path (optional)
  - **[--language]**: Language code in ISO-639-3 (i.e.: ita for italian, eng for english, deu for german...).<br>
    Default language is eng and --language is optional for default language set in ./lib/lang.py.<br>
    The ISO-639-1 2 letters codes are also supported.


###  Example of Custom Model Zip Upload
  (must be a .zip file containing the mandatory model files. Example for XTTSv2: config.json, model.pth, vocab.json and ref.wav)
   - **Linux/MacOS**
     ```bash
     ./ebook2audiobook.command --headless --ebook <ebook_file_path> --language <language> --custom_model <custom_model_path>
     ```
   - **Windows**
     ```bash
     ebook2audiobook.cmd --headless --ebook <ebook_file_path> --language <language> --custom_model <custom_model_path>
     ```
     <i>Note: the ref.wav of your custom model is always the voice selected for the conversion</i>
     
- **<custom_model_path>**: Path to `model_name.zip` file,
      which must contain (according to the tts engine) all the mandatory files<br>
      (see ./lib/models.py).

### For Detailed Guide with list of all Parameters to use
   - **Linux/MacOS**
     ```bash
     ./ebook2audiobook.command --help
     ```
   - **Windows**
     ```bash
     ebook2audiobook.cmd --help
     ```
   - **Or for all OS**
    ```python
     app.py --help
    ```

<a id="help-command-output"></a>
```bash
usage: app.py [-h] [--session SESSION] [--share] [--headless] [--ebook EBOOK] [--ebooks_dir EBOOKS_DIR]
              [--language LANGUAGE] [--voice VOICE] [--device {CPU,CUDA,MPS,ROCM,XPU,JETSON}]
              [--tts_engine {XTTSv2,BARK,VITS,FAIRSEQ,TACOTRON2,YOURTTS,xtts,bark,vits,fairseq,tacotron,yourtts}]
              [--custom_model CUSTOM_MODEL] [--fine_tuned FINE_TUNED] [--output_format OUTPUT_FORMAT]
              [--output_channel OUTPUT_CHANNEL] [--temperature TEMPERATURE] [--length_penalty LENGTH_PENALTY]
              [--num_beams NUM_BEAMS] [--repetition_penalty REPETITION_PENALTY] [--top_k TOP_K] [--top_p TOP_P]
              [--speed SPEED] [--enable_text_splitting] [--text_temp TEXT_TEMP] [--waveform_temp WAVEFORM_TEMP]
              [--output_dir OUTPUT_DIR] [--version]

Convert eBooks to Audiobooks using a Text-to-Speech model. You can either launch the Gradio interface or run the script in headless mode for direct conversion.

options:
  -h, --help            show this help message and exit
  --session SESSION     Session to resume the conversion in case of interruption, crash,
                            or reuse of custom models and custom cloning voices.

**** The following options are for all modes:
  Optional

**** The following option are for gradio/gui mode only:
  Optional

  --share               Enable a public shareable Gradio link.

**** The following options are for --headless mode only:
  --headless            Run the script in headless mode
  --ebook EBOOK         Path to the ebook file for conversion. Cannot be used when --ebooks_dir is present.
  --ebooks_dir EBOOKS_DIR
                        Relative or absolute path of the directory containing the files to convert.
                            Cannot be used when --ebook is present.
  --text TEXT           Raw text for conversion. Cannot be used when --ebook or --ebooks_dir is present.
  --language LANGUAGE   Language of the e-book. Default language is set
                            in ./lib/lang.py sed as default if not present. All compatible language codes are in ./lib/lang.py

optional parameters:
  --voice VOICE         (Optional) Path to the voice cloning file for TTS engine.
                            Uses the default voice if not present.
  --device {CPU,CUDA,MPS,ROCM,XPU,JETSON}
                        (Optional) Processor unit type for the conversion.
                            Default is set in ./lib/conf.py if not present. Fall back to CPU if CUDA or MPS is not available.
  --tts_engine {XTTSv2,BARK,VITS,FAIRSEQ,TACOTRON2,YOURTTS,xtts,bark,vits,fairseq,tacotron,yourtts}
                        (Optional) Preferred TTS engine (available are: ['XTTSv2', 'BARK', 'VITS', 'FAIRSEQ', 'TACOTRON2', 'YOURTTS', 'FISHSPEECH', 'xtts', 'bark', 'vits', 'fairseq', 'tacotron', 'yourtts', 'fishspeech'].
                            Default depends on the selected language. The tts engine should be compatible with the chosen language
  --custom_model CUSTOM_MODEL
                        (Optional) Path to the custom model zip file cntaining mandatory model files.
                            Please refer to ./lib/models.py
  --fine_tuned FINE_TUNED
                        (Optional) Fine tuned model path. Default is builtin model.
  --output_format OUTPUT_FORMAT
                        (Optional) Output audio format. Default is m4b set in ./lib/conf.py
  --output_channel OUTPUT_CHANNEL
                        (Optional) Output audio channel. Default is mono set in ./lib/conf.py
  --temperature TEMPERATURE
                        (xtts only, optional) Temperature for the model.
                            Default to config.json model. Higher temperatures lead to more creative outputs.
  --length_penalty LENGTH_PENALTY
                        (xtts only, optional) A length penalty applied to the autoregressive decoder.
                            Default to config.json model. Not applied to custom models.
  --num_beams NUM_BEAMS
                        (xtts only, optional) Controls how many alternative sequences the model explores. Must be equal or greater than length penalty.
                            Default to config.json model.
  --repetition_penalty REPETITION_PENALTY
                        (xtts only, optional) A penalty that prevents the autoregressive decoder from repeating itself.
                            Default to config.json model.
  --top_k TOP_K         (xtts only, optional) Top-k sampling.
                            Lower values mean more likely outputs and increased audio generation speed.
                            Default to config.json model.
  --top_p TOP_P         (xtts only, optional) Top-p sampling.
                            Lower values mean more likely outputs and increased audio generation speed. Default to config.json model.
  --speed SPEED         (xtts only, optional) Speed factor for the speech generation.
                            Default to config.json model.
  --enable_text_splitting
                        (xtts only, optional) Enable TTS text splitting. This option is known to not be very efficient.
                            Default to config.json model.
  --text_temp TEXT_TEMP
                        (bark only, optional) Text Temperature for the model.
                            Default to config.json model.
  --waveform_temp WAVEFORM_TEMP
                        (bark only, optional) Waveform Temperature for the model.
                            Default to config.json model.
  --output_dir OUTPUT_DIR
                        (Optional) Path to the output directory. Default is set in ./lib/conf.py
  --version             Show the version of the script and exit

Example usage:
Windows:
    Gradio/GUI:
    ebook2audiobook.cmd
    Headless mode:
    ebook2audiobook.cmd --headless --ebook '/path/to/file' --language eng
Linux/Mac:
    Gradio/GUI:
    ./ebook2audiobook.command
    Headless mode:
    ./ebook2audiobook.command --headless --ebook '/path/to/file' --language eng

SML tags available:
        [break] — silence (random range **0.3–0.6 sec.**)
        [pause] — silence (random range **1.0–1.6 sec.**)
        [pause:N] — fixed pause (**N sec.**)
        [voice:/path/to/voice/file]...[/voice] — switch voice from default or selected voice from GUI/CLI

```

NOTE: in gradio/gui mode, to cancel a running conversion, just click on the [X] from the ebook upload component.
TIP: if it needs some more pause, add '[pause:3]' for 3 sec. etc.

### Docker
1. **Clone the Repository**:
```bash
   git clone https://github.com/DrewThomasson/ebook2audiobook.git
   cd ebook2audiobook
```
2. **Build the container**
```bash
    Windows:
        Docker:
            ebook2audiobook.cmd --script_mode build_docker
        Docker Compose:
            ebook2audiobook.cmd --script_mode build_docker --docker_mode compose
        Podman Compose:
            ebook2audiobook.cmd --script_mode build_docker --docker_mode podman
    Linux/Mac
        Docker:
            ./ebook2audiobook.command --script_mode build_docker
        Docker Compose
            ./ebook2audiobook.command --script_mode build_docker --docker_mode compose
        Podman Compose:
            ./ebook2audiobook.command --script_mode build_docker --docker_mode podman
```
4. **Run the Container:**
```bash
Docker run image:
    Gradio/GUI:
        CPU:
          docker run -v "./ebooks:/app/ebooks" -v "./audiobooks:/app/audiobooks" -v "./models:/app/models" -v "./voices:/app/voices" -v "./tmp:/app/tmp" --rm -it -p 7860:7860 athomasson2/ebook2audiobook:cpu
        CUDA:
          docker run -v "./ebooks:/app/ebooks" -v "./audiobooks:/app/audiobooks" -v "./models:/app/models" -v "./voices:/app/voices" -v "./tmp:/app/tmp" --gpus all --rm -it -p 7860:7860 athomasson2/ebook2audiobook:cu[118/122/124/126 etc..]
        ROCM:
          docker run -v "./ebooks:/app/ebooks" -v "./audiobooks:/app/audiobooks" -v "./models:/app/models" -v "./voices:/app/voices" -v "./tmp:/app/tmp" --device=/dev/kfd --device=/dev/dri --rm -it -p 7860:7860 athomasson2/ebook2audiobook:rocm[6.0/6.1/6.4 etc..]
        XPU:
          docker run -v "./ebooks:/app/ebooks" -v "./audiobooks:/app/audiobooks" -v "./models:/app/models" -v "./voices:/app/voices" -v "./tmp:/app/tmp" --device=/dev/dri --rm -it -p 7860:7860 athomasson2/ebook2audiobook:xpu
        JETSON:
          docker run -v "./ebooks:/app/ebooks" -v "./audiobooks:/app/audiobooks" -v "./models:/app/models" -v "./voices:/app/voices" -v "./tmp:/app/tmp" --runtime nvidia  --rm -it -p 7860:7860 athomasson2/ebook2audiobook:jetson[51/60/61 etc...]
    Headless mode:
        CPU:
          docker run -v "./ebooks:/app/ebooks" -v "./audiobooks:/app/audiobooks" -v "./models:/app/models" -v "./voices:/app/voices" -v "./tmp:/app/tmp" -v "/my/real/ebooks/folder/absolute/path:/app/another_ebook_folder" --rm -it -p 7860:7860 ebook2audiobook:cpu --headless --ebook "/app/another_ebook_folder/myfile.pdf" [--voice /app/my/voicepath/voice.mp3 etc..]
        CUDA:
          docker run -v "./ebooks:/app/ebooks" -v "./audiobooks:/app/audiobooks" -v "./models:/app/models" -v "./voices:/app/voices" -v "./tmp:/app/tmp" -v "/my/real/ebooks/folder/absolute/path:/app/another_ebook_folder" --gpus all --rm -it -p 7860:7860 ebook2audiobook:cu[118/122/124/126 etc..] --headless --ebook "/app/another_ebook_folder/myfile.pdf" [--voice /app/my/voicepath/voice.mp3 etc..]
        ROCM:
          docker run -v "./ebooks:/app/ebooks" -v "./audiobooks:/app/audiobooks" -v "./models:/app/models" -v "./voices:/app/voices" -v "./tmp:/app/tmp" -v "/my/real/ebooks/folder/absolute/path:/app/another_ebook_folder" --device=/dev/kfd --device=/dev/dri --rm -it -p 7860:7860 ebook2audiobook:rocm[6.0/6.1/6.4 etc.] --headless --ebook "/app/another_ebook_folder/myfile.pdf" [--voice /app/my/voicepath/voice.mp3 etc..]
        XPU:
          docker run -v "./ebooks:/app/ebooks" -v "./audiobooks:/app/audiobooks" -v "./models:/app/models" -v "./voices:/app/voices" -v "./tmp:/app/tmp" -v "/my/real/ebooks/folder/absolute/path:/app/another_ebook_folder" --device=/dev/dri --rm -it -p 7860:7860 ebook2audiobook:xpu --headless --ebook "/app/another_ebook_folder/myfile.pdf" [--voice /app/my/voicepath/voice.mp3 etc..]
        JETSON:
          docker run -v "./ebooks:/app/ebooks" -v "./audiobooks:/app/audiobooks" -v "./models:/app/models" -v "./voices:/app/voices" -v "./tmp:/app/tmp" -v "/my/real/ebooks/folder/absolute/path:/app/another_ebook_folder" --runtime nvidia --rm -it -p 7860:7860 ebook2audiobook:jetson[51/60/61 etc.] --headless --ebook "/app/another_ebook_folder/myfile.pdf" [--voice /app/my/voicepath/voice.mp3 etc..]
Docker Compose (i.e. cuda 12.8:
        Run Gradio GUI:
               DEVICE_TAG=cu128 docker compose --profile gpu up --no-log-prefix
        Run Headless mode:
               DEVICE_TAG=cu128 docker compose --profile gpu run --rm ebook2audiobook --headless --ebook "/app/ebooks/myfile.pdf" --voice /app/voices/eng/adult/female/some_voice.wav etc..
Podman Compose (i.e. cuda 12.8:
        Run Gradio GUI:
               DEVICE_TAG=cu128 podman-compose -f podman-compose.yml --profile gpu up
        Run Headless mode:
               DEVICE_TAG=cu128 podman-compose -f podman-compose.yml --profile gpu run --rm ebook2audiobook-gpu --headless --ebook "/app/ebooks/myfile.pdf" --voice /app/voices/eng/adult/female/some_voice.wav etc..
```
- NOTE: MPS is not exposed in docker so CPU must be used
  
### Common Docker Issues
- My NVIDIA GPU isn't being detected?? -> [GPU ISSUES Wiki Page](https://github.com/DrewThomasson/ebook2audiobook/wiki/GPU-ISSUES)

## Fine Tuned TTS models
#### Fine Tune your own XTTSv2 model

[![Hugging Face](https://img.shields.io/badge/Hugging%20Face-Spaces-yellow?style=flat&logo=huggingface)](https://huggingface.co/spaces/drewThomasson/xtts-finetune-webui-gpu) [![Kaggle](https://img.shields.io/badge/Kaggle-035a7d?style=flat&logo=kaggle&logoColor=white)](https://github.com/DrewThomasson/ebook2audiobook/blob/v25/Notebooks/finetune/xtts/kaggle-xtts-finetune-webui-gradio-gui.ipynb) [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/DrewThomasson/ebook2audiobook/blob/v25/Notebooks/finetune/xtts/colab_xtts_finetune_webui.ipynb)


#### De-noise training data

[![Hugging Face](https://img.shields.io/badge/Hugging%20Face-Spaces-yellow?style=flat&logo=huggingface)](https://huggingface.co/spaces/drewThomasson/DeepFilterNet2_no_limit) [![GitHub Repo](https://img.shields.io/badge/DeepFilterNet-181717?logo=github)](https://github.com/Rikorose/DeepFilterNet)


### Fine Tuned TTS Collection

[![Hugging Face](https://img.shields.io/badge/Hugging%20Face-Models-yellow?style=flat&logo=huggingface)](https://huggingface.co/drewThomasson/fineTunedTTSModels/tree/main)

For an XTTSv2 custom model a ref audio clip of the voice reference is mandatory:

## Your own Ebook2Audiobook customization
You are free to modify libs/conf.py to add or remove the settings you wish. If you plan to do it just make
a copy of the original conf.py so on each ebook2audiobook update you will backup your modified conf.py and put
back the original one. You must plan the same process for models.py. If you wish to make your own custom model
as an official ebook2audiobook fine tuned model so please contact us and we'll add it to the presets list.

## Reverting to older Versions
Releases can be found -> [here](https://github.com/DrewThomasson/ebook2audiobook/releases)
```bash
git checkout tags/VERSION_NUM # Locally/Compose -> Example: git checkout tags/v25.7.7
```

## Common Issues:
- My NVIDIA/ROCm/XPU/MPS GPU isn't being detected?? -> [GPU ISSUES Wiki Page](https://github.com/DrewThomasson/ebook2audiobook/wiki/GPU-ISSUES)
-  CPU is slow (better on server smp CPU) while GPU can have almost real time conversion.
   [Discussion about this](https://github.com/DrewThomasson/ebook2audiobook/discussions/19#discussioncomment-10879846)
   For faster multilingual generation I would suggest my other
   [project that uses piper-tts](https://github.com/DrewThomasson/ebook2audiobookpiper-tts) instead
   (It doesn't have zero-shot voice cloning though, and is Siri quality voices, but it is much faster on cpu).
- "I'm having dependency issues" - Just use the docker, its fully self contained and has a headless mode,
   add `--help` parameter at the end of the docker run command for more information.
- "Im getting a truncated audio issue!" - PLEASE MAKE AN ISSUE OF THIS,
   we don't speak every language and need advise from users to fine tune the sentence splitting logic.😊


## What we need help with! 🙌 
## [Roadmap and Full list of things can be found here](https://github.com/DrewThomasson/ebook2audiobook/issues/32)
- Any help from people speaking any of the supported languages to help us improve the models

---

## Modern Web UI

A second, fully standalone web interface built with **React + TypeScript + Tailwind** (frontend) and **FastAPI** (backend, port 8000) ships alongside the existing Gradio UI.

### Features
- **Upload → Configure → Chapters Editor → Convert → Library** — guided single-page flow
- **Live progress via Server-Sent Events (SSE)** — per-sentence status streamed to the browser without polling
- **Voice Browser & Preview** — browse and audition built-in voices before committing
- **Audiobook Library** — completed audiobooks and in-progress sessions listed with date, UUID, and a *Finish & Combine* button for sessions that completed TTS but lost the final combine step
- **Session resume** — sessions survive server restarts; incomplete conversions can be continued exactly where they left off
- **REST API**
  - `POST /api/sessions` — create session (upload ebook)
  - `GET /api/sessions/{id}/events` — SSE stream
  - `POST /api/sessions/{id}/combine` — combine chapter audio for a stalled session
  - `DELETE /api/sessions/{id}` — clean up tmp files, proc dir, and uploaded ebook

### Starting the Web UI
```bash
# Backend (from repo root)
uvicorn webui.backend.main:app --port 8000 --reload

# Frontend (first time: npm install)
cd webui/frontend
npm run dev        # dev server on :5173
npm run build      # production build → dist/
```

---

## Additional Engines

The three optional high-quality engines — **Fish Speech 1.5**, **CosyVoice 3**, and **Qwen3-TTS** — are not included in the default install because they carry large dependencies or require a separate package ecosystem. Each must be installed once; after that the Web UI will expose it automatically.

### Fish Speech 1.5

Zero-shot voice cloning (~88–92% similarity). **Non-commercial use only** ([CC-BY-NC-SA-4.0](https://huggingface.co/fishaudio/fish-speech-1.5)).

```bash
# Linux / macOS
pip install fish-speech

# Windows (CUDA)
pip install fish-speech
```

Then start the app normally — the `Fish Speech 1.5` option will appear in the engine dropdown.

---

### CosyVoice 3

Zero-shot voice cloning with cross-lingual and instruct mode. **Apache 2.0, commercial use allowed.**

```bash
# Clone the third-party submodule (one-time)
git clone --recursive https://github.com/FunAudioLLM/CosyVoice third_party/CosyVoice
pip install -r third_party/CosyVoice/requirements.txt
```

Activate in the Web UI: write `cosyvoice` to `.engine-mode` in the repo root, or select it from the engine dropdown (shown only when the mode file is present).

> **Note**: CosyVoice has a known upstream incompatibility with recent versions of certain dependencies. See [upstream issue #1422](https://github.com/FunAudioLLM/CosyVoice/issues/1422) for status.

---

### Qwen3-TTS

Zero-shot voice cloning via Alibaba's Qwen3 transformer TTS. **Apache 2.0, commercial use allowed.**

**Requirements**: ~6 GB VRAM (bfloat16), CUDA 11.8+. Model weights download automatically on first run (~3 GB from HuggingFace).

```bash
pip install -U qwen-tts
```

Activate in the Web UI by writing `qwen3tts` to `.engine-mode` in the repo root:

```bash
# Linux / macOS
echo "qwen3tts" > .engine-mode

# Windows (PowerShell)
"qwen3tts" | Out-File -Encoding ascii .engine-mode
```

The `Qwen3-TTS` option will appear in the engine dropdown. Select a reference voice (`.wav`) in the Voice field — Qwen3-TTS clones the speaker style from that file without requiring a transcript.

**Supported languages**: Arabic, German, English, French, Italian, Japanese, Korean, Portuguese, Russian, Spanish, Chinese.

---

## Performance Improvements

All 9 TTS engines (`XTTSv2`, `Bark`, `VITS`, `Fairseq`, `Tacotron2`, `Tortoise`, `GlowTTS`, `YourTTS`, `Fish Speech 1.5`) received GPU inference optimizations. The changes are cumulative and hardware-adaptive — they activate only when the detected GPU supports them.

### GPU-Resident Model (all 8 engines)

**The single biggest speedup.** Previously each engine shuffled its full model weight set GPU→CPU→GPU on every sentence (or even every sub-sentence part). The model is now moved to the target device **once per conversion job** and stays there.

On a typical RTX 40-series card a 1.8 GB model (e.g. XTTSv2) costs ~110 ms per transfer direction over PCIe. For a 10,000-sentence audiobook the old behaviour wasted **~36 minutes** of pure memory transfer with zero benefit. That overhead is now zero.

### `torch.inference_mode()` (all 8 engines)

Replaced `torch.no_grad()` with `torch.inference_mode()` across every engine's hot path. `inference_mode` additionally disables per-tensor version-counter tracking, saving ~10% wall-clock on autoregressive models with long token sequences.

### Hardware Acceleration: TF32 + Flash Attention (Ampere / Ada Lovelace)

Enabled at engine load time, conditioned on runtime GPU detection:

| Feature | Condition | Benefit |
|---|---|---|
| **TF32 matmul** | CUDA, CC ≥ 8.0 (RTX 30xx/40xx), non-Jetson | Native tensor-core throughput for FP32 ops |
| **TF32 cuDNN** | Same | Convolution speedup |
| **Flash SDP** | CC ≥ 8.0 | Hardware-fused attention, lower memory bandwidth |
| **Memory-Efficient SDP** | CC ≥ 8.0 | Reduced VRAM for large attention matrices |
| **BF16 autocast** | CC ≥ 8.0, non-Windows | Halved memory, tensor-core paths for matmul |
| **FP16 autocast** | CC ≥ 7.0, or Windows | Safe precision reduction on older / Windows targets |

All flags are wrapped in `try/except` and fall back silently to FP32 on unsupported hardware.

### `torch.compile()` on Checkpoint-Loaded Engines

Applied to XTTSv2 after checkpoint load when running on GPU (PyTorch ≥ 2.0). The model graph is compiled into fused CUDA kernels on the first inference call (`mode='reduce-overhead'`, `fullgraph=False` to tolerate XTTS dynamic control flow). Pays a ~30 s warmup on sentence 1; all subsequent sentences skip Python dispatch overhead entirely.

### Hot-Path Micro-Optimisations (XTTSv2)

- **Invariant hoisting** — `fine_tuned_params` dict, `language_iso1`, `amp_enabled`, and `samplerate` were rebuilt on every sentence-part; now computed once per `convert()` call.
- **SML fast-path** — `_split_sentence_on_sml()` skips the regex `finditer` entirely when the sentence contains no `[` character (the common case for plain prose).
- **Silence tensor cache** — silence-break tensors (~10–30 KB each) were freshly allocated for every sentence-part. Now cached by sample count and reused. Eliminates ~300 MB of allocation churn on a 10,000-sentence book.
- **Pre-compiled regex** — the trailing-word check `r'\w$'` is compiled once at module load rather than on every sentence-part.
- **O(1) dict membership** — `key in dict` replaces `key in dict.keys()` throughout all engine hot paths.

### Skip Redundant `cleanup_memory()` on Cache Hit

`cleanup_memory()` (which calls `torch.cuda.empty_cache()` + Windows working-set trim) previously ran unconditionally before every model load, even when the model was already warm in the cache. It now runs only on genuine cold loads.

### WAV as Default Intermediate Format

Changed `default_audio_proc_format` from `flac` to `wav` in `lib/conf.py`. FLAC encoding is CPU-bound; for thousands of per-sentence segment files it added measurable latency between GPU inference calls. WAV is a direct PCM dump — zero encoding overhead.

### Optional DeepSpeed Inference

`XTTSv2` and `Bark` attempt `deepspeed.init_inference()` after model load when DeepSpeed is installed. On systems with the full CUDA Toolkit this enables kernel-injected, multi-precision inference fusion. On systems without DeepSpeed (or without `nvcc`) the engines fall back to standard PyTorch automatically — no configuration required.

---
  
<!--
## Do you need to rent a GPU to boost service from us?
- A poll is open here https://github.com/DrewThomasson/ebook2audiobook/discussions/889
-->

## Special Thanks
- **Coqui TTS**: [Coqui TTS GitHub](https://github.com/idiap/coqui-ai-TTS)
- **Calibre**: [Calibre Website](https://calibre-ebook.com)
- **FFmpeg**: [FFmpeg Website](https://ffmpeg.org)
- [@shakenbake15 for better chapter saving method](https://github.com/DrewThomasson/ebook2audiobook/issues/8) 
