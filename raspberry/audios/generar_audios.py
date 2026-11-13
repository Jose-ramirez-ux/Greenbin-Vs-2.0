import asyncio
import edge_tts

VOZ = "es-CO-SalomeNeural"   # o "es-CO-GonzaloNeural" para voz masculina

MENSAJES = {
    "organico":        "Residuo orgánico. Deposítalo en la caneca verde.",
    "aprovechable":    "Residuo aprovechable. Deposítalo en la caneca blanca.",
    "no_aprovechable": "Residuo no aprovechable. Deposítalo en la caneca negra.",
    "desconocido":     "No pude identificar el residuo. Acércalo de nuevo a la cámara.",
}

async def main():
    for clase, texto in MENSAJES.items():
        await edge_tts.Communicate(texto, VOZ).save(f"{clase}.mp3")
        print(f"Generado: {clase}.mp3")

asyncio.run(main())