import asyncio
import edge_tts

async def main():
    comm = edge_tts.Communicate("Hello world this is a test.", "en-US-ChristopherNeural")
    types = []
    async for c in comm.stream():
        types.append(c["type"])
        if c["type"] != "audio":
            print("NON-AUDIO EVENT:", c)
    print("ALL TYPES FOUND:", set(types))

asyncio.run(main())
