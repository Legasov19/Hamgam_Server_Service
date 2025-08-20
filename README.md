Command For Release:pyinstaller --noconfirm --onefile --name Hamgam --icon=webcom.ico --add-data "static;static" --exclude-module torch --exclude-module transformers --exclude-module tensorflow --exclude-module pandas --exclude-module grpc --exclude-module sentencepiece --exclude-module zstandard app.py
cloudflared: PS D:\Python Hamgam\ProjectHamgam> & "C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel run pwa-tunnel

How To install cloudflared :
PS C:\Users\PicoNet> winget install --id Cloudflare.cloudflared
(C:\Program Files (x86)\cloudflared.exe  Copy this path)
PS C:\Users\PicoNet> cloudflared tunnel login
PS C:\Users\PicoNet> cloudflared --version
PS C:\Users\PicoNet> & "C:\Program Files\Cloudflared\cloudflared.exe" tunnel login
"C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel create pwa-tunnel
"C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel route dns pwa-tunnel hamgam-web.ir
"C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel route dns pwa-tunnel pwa.hamgam-web.ir