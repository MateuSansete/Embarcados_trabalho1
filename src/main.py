#!/usr/bin/env python3
"""
main.py — Controlador principal do sistema de semáforos (Entrega 1).

Inicializa o módulo GPIO e executa os dois modelos de semáforo em paralelo:
  - Modelo 1: Semáforo simples com 3 LEDs (Cruzamento 1)
  - Modelo 2: Cruzamento completo com código de 3 bits (Cruzamento 2)

Uso:
  python3 -m src.main              # Executa ambos os modelos
  python3 -m src.main --modelo 1   # Executa apenas o Modelo 1
  python3 -m src.main --modelo 2   # Executa apenas o Modelo 2

O programa trata SIGINT (Ctrl+C) para encerrar os semáforos de forma
graciosa, desligando todos os LEDs e liberando os recursos GPIO.
"""

import argparse
import signal
import sys
import time

from src.gpio_module import GPIOController
from src.traffic_light_model1 import TrafficLightModel1
from src.traffic_light_model2 import TrafficLightModel2


def parse_args() -> argparse.Namespace:
    """
    Processa argumentos de linha de comando.

    Returns:
        Namespace com o atributo `modelo` (None, 1 ou 2).
    """
    parser = argparse.ArgumentParser(
        description="Sistema de Controle de Semáforos — Entrega 1 (FSE 2026/1)",
    )
    parser.add_argument(
        "--modelo",
        type=int,
        choices=[1, 2],
        default=None,
        help="Executa apenas o modelo especificado (1 ou 2). "
        "Se omitido, executa ambos.",
    )
    return parser.parse_args()


def main() -> None:
    """
    Ponto de entrada principal.

    1. Inicializa o controlador GPIO.
    2. Cria e inicia as threads dos modelos solicitados.
    3. Aguarda indefinidamente (Ctrl+C para encerrar).
    4. Encerra tudo de forma graciosa.
    """
    args = parse_args()

    print("=" * 60, flush=True)
    print("  SISTEMA DE CONTROLE DE SEMÁFOROS — ENTREGA 1", flush=True)
    print("  Fundamentos de Sistemas Embarcados (2026/1)", flush=True)
    print("=" * 60, flush=True)

    # Inicializar GPIO
    gpio = GPIOController()
    print("[Sistema] GPIO inicializada (modo BCM).", flush=True)

    # Lista de modelos ativos para controle de shutdown
    active_models: list = []

    # --- Modelo 1 ---
    if args.modelo is None or args.modelo == 1:
        model1 = TrafficLightModel1(gpio)
        model1.start()
        active_models.append(model1)
        print("[Sistema] Modelo 1 (3 LEDs) iniciado.", flush=True)

    # --- Modelo 2 ---
    if args.modelo is None or args.modelo == 2:
        model2 = TrafficLightModel2(gpio)
        model2.start()
        active_models.append(model2)
        print("[Sistema] Modelo 2 (Cruzamento 3-bit) iniciado.", flush=True)

    print("-" * 60, flush=True)
    print("[Sistema] Pressione Ctrl+C para encerrar.", flush=True)
    print("-" * 60, flush=True)

    # Handler de sinal para shutdown gracioso
    def shutdown_handler(signum, frame):
        """Trata SIGINT/SIGTERM para encerramento limpo."""
        print("\n[Sistema] Sinal de encerramento recebido. Parando...", flush=True)
        for model in active_models:
            model.stop()
        gpio.cleanup()
        print("[Sistema] GPIO liberada. Encerrando.", flush=True)
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    # Loop principal — mantém a thread principal viva
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        # Fallback caso o handler de sinal não capture
        shutdown_handler(None, None)


if __name__ == "__main__":
    main()
