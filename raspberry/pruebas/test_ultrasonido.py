from gpiozero import DistanceSensor
from time import sleep

sensor = DistanceSensor(echo=24, trigger=23, max_distance=4)

print("Midiendo... (Ctrl + C para detener)")
while True:
    print(f"Distancia: {sensor.distance * 100:.1f} cm")
    sleep(0.5)
