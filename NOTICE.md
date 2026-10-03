# Third-party notes

The ShelfSense application code, shelf icon, sample price list, and sample store SOP in this repository are original.

This repo does not vendor third-party source, model weights, or product manuals.

- Android libraries (AndroidX, CameraX, ML Kit, Room, WorkManager, Retrofit, OkHttp, Koin) are downloaded by Gradle when you build. They are not copied into this repository. ML Kit runs on the device under Google's library terms.
- Python libraries in `server/requirements.txt` are installed into a virtual environment. Do not commit that environment.
- `llama3.2:3b` is not included. If you pull it with Ollama, Meta's Llama 3.2 Community License applies to the weights, which stay on your machine.
- Sample barcodes are generic UPC-A numbers with plain product descriptions (for example "Cola 12pk Cans"). They are not brand artwork or copied catalog copy.
- The hardware-scanner intent names (`com.symbol.datawedge.*`) are the public intent contract used by some rugged Android scanners. ShelfSense does not include that vendor's software.
