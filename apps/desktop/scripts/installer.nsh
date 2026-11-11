; 安装时在安装目录创建 model/，供用户放入本地 CTranslate2 模型。
; 工作台会按安装位置自动扫描该目录，用户无需手写 manifest.json。
!macro customInstall
  CreateDirectory "$INSTDIR\model"
  FileOpen $0 "$INSTDIR\model\放置模型说明.txt" w
  FileWrite $0 "Whisper工作台 模型放置说明$\r$\n"
  FileWrite $0 "==============================$\r$\n"
  FileWrite $0 "1. 在本目录下为每个 CTranslate2 Whisper 模型建一个子目录，例如：$\r$\n"
  FileWrite $0 "   $INSTDIR\model\whisper-ja-1.5B\$\r$\n"
  FileWrite $0 "2. 每个模型子目录需包含：model.bin、config.json、tokenizer.json、$\r$\n"
  FileWrite $0 "   preprocessor_config.json、vocabulary.json。$\r$\n"
  FileWrite $0 "3. VAD 文件 whisper_vad.onnx 与 whisper_vad_metadata.json 放在本目录根。$\r$\n"
  FileWrite $0 "4. 模型权重由用户自行准备，工作台不会自动下载。$\r$\n"
  FileWrite $0 "5. 放好后在应用「设置」页点击「重新扫描」即可识别。$\r$\n"
  FileClose $0
!macroend

; 卸载时保留用户放入的模型文件，不主动删除 model/ 目录。
!macro customUnInstall
  ; 有意留空：避免删除用户准备的模型资产。
!macroend
