"""
traffic_light_model1.py — Máquina de estados do Modelo 1 (Semáforo Simples).

Controla 3 LEDs individuais (verde, amarelo, vermelho) no Cruzamento 1.
Ciclo: VERDE (10s) → AMARELO (2s) → VERMELHO (10s) → VERDE ...

Regra de pedestre:
  - Se VERDE e tempo mínimo (5s) já passou → troca imediatamente para AMARELO.
  - Se VERDE e tempo mínimo NÃO passou → aguarda completar 5s e então troca.
  - Se AMARELO ou VERMELHO → botão ignorado.
"""

import threading
import time
from enum import Enum

from src.config import (
    LOOP_INTERVAL,
    M1_GPIO_BTN_CRUZAMENTO,
    M1_GPIO_BTN_PRINCIPAL,
    M1_GPIO_GREEN,
    M1_GPIO_RED,
    M1_GPIO_YELLOW,
    M1_GREEN_MIN_TIME,
    M1_GREEN_TIME,
    M1_RED_TIME,
    M1_YELLOW_TIME,
)
from src.gpio_module import GPIOController


class Model1State(Enum):
    """Estados da máquina de estados do Modelo 1."""

    GREEN = "VERDE"
    YELLOW = "AMARELO"
    RED = "VERMELHO"


class TrafficLightModel1(threading.Thread):
    """
    Semáforo simples com 3 LEDs individuais.

    Roda em thread própria. O loop principal verifica a cada LOOP_INTERVAL
    se é hora de transicionar de estado, considerando o tempo decorrido
    e eventuais pedidos de pedestre.
    """

    def __init__(self, gpio: GPIOController):
        """
        Inicializa o semáforo Modelo 1.

        Args:
            gpio: Instância compartilhada do controlador GPIO.
        """
        super().__init__(daemon=True, name="Model1-Thread")
        self._gpio = gpio
        self._running = threading.Event()
        self._pedestrian_requested = threading.Event()

        # Estado inicial
        self._state = Model1State.GREEN
        self._state_start: float = 0.0

        # Configurar pinos de saída
        self._gpio.setup_output(M1_GPIO_GREEN)
        self._gpio.setup_output(M1_GPIO_YELLOW)
        self._gpio.setup_output(M1_GPIO_RED)

        # Configurar pinos de entrada (botões)
        self._gpio.setup_input(M1_GPIO_BTN_PRINCIPAL)
        self._gpio.setup_input(M1_GPIO_BTN_CRUZAMENTO)

        # Registrar callbacks de botão com debounce
        self._gpio.register_callback(
            M1_GPIO_BTN_PRINCIPAL, self._on_button_principal
        )
        self._gpio.register_callback(
            M1_GPIO_BTN_CRUZAMENTO, self._on_button_cruzamento
        )

    # -----------------------------------------------------------------
    # Callbacks de botão (executados na thread de interrupção do RPi.GPIO)
    # -----------------------------------------------------------------

    def _on_button_principal(self, channel: int) -> None:
        """Callback do botão de pedestre principal (GPIO 1)."""
        print(f"[Modelo 1] Botão pedestre principal acionado (GPIO {channel})")
        self._pedestrian_requested.set()

    def _on_button_cruzamento(self, channel: int) -> None:
        """Callback do botão de pedestre cruzamento (GPIO 12)."""
        print(f"[Modelo 1] Botão pedestre cruzamento acionado (GPIO {channel})")
        self._pedestrian_requested.set()

    # -----------------------------------------------------------------
    # Controle de LEDs
    # -----------------------------------------------------------------

    def _set_leds(self, green: bool, yellow: bool, red: bool) -> None:
        """
        Define o estado dos 3 LEDs.

        Args:
            green: True para acender o LED verde.
            yellow: True para acender o LED amarelo.
            red: True para acender o LED vermelho.
        """
        self._gpio.write(M1_GPIO_GREEN, green)
        self._gpio.write(M1_GPIO_YELLOW, yellow)
        self._gpio.write(M1_GPIO_RED, red)

    def _apply_state(self) -> None:
        """Aplica o estado atual nos LEDs GPIO."""
        if self._state == Model1State.GREEN:
            self._set_leds(green=True, yellow=False, red=False)
        elif self._state == Model1State.YELLOW:
            self._set_leds(green=False, yellow=True, red=False)
        elif self._state == Model1State.RED:
            self._set_leds(green=False, yellow=False, red=True)

    # -----------------------------------------------------------------
    # Transição de estados
    # -----------------------------------------------------------------

    def _transition_to(self, new_state: Model1State) -> None:
        """
        Realiza a transição para um novo estado.

        Imprime a mudança no terminal, atualiza os LEDs e reseta o
        timestamp e a flag de pedestre.

        Args:
            new_state: Próximo estado da FSM.
        """
        old_name = self._state.value
        new_name = new_state.value
        print(f"[Modelo 1] {old_name} → {new_name}")

        self._state = new_state
        self._state_start = time.monotonic()
        self._pedestrian_requested.clear()
        self._apply_state()

    # -----------------------------------------------------------------
    # Loop principal da FSM
    # -----------------------------------------------------------------

    def run(self) -> None:
        """
        Loop principal da thread — executa a máquina de estados.

        A cada iteração (LOOP_INTERVAL ≈ 50ms):
          1. Calcula o tempo decorrido no estado atual.
          2. Verifica condições de transição (tempo + botão).
          3. Dorme pelo intervalo configurado.
        """
        self._running.set()
        self._state_start = time.monotonic()
        self._apply_state()
        print(f"[Modelo 1] Iniciado no estado {self._state.value}")

        while self._running.is_set():
            elapsed = time.monotonic() - self._state_start

            if self._state == Model1State.GREEN:
                # Botão pedestre: antecipa se tempo mínimo já passou
                if self._pedestrian_requested.is_set():
                    if elapsed >= M1_GREEN_MIN_TIME:
                        self._transition_to(Model1State.YELLOW)
                        continue
                    # Se ainda não passou o mínimo, a flag fica pendente
                    # e será verificada na próxima iteração.

                # Tempo máximo do verde esgotado
                if elapsed >= M1_GREEN_TIME:
                    self._transition_to(Model1State.YELLOW)
                    continue

                # Caso especial: botão pendente e atingiu tempo mínimo
                if self._pedestrian_requested.is_set() and elapsed >= M1_GREEN_MIN_TIME:
                    self._transition_to(Model1State.YELLOW)
                    continue

            elif self._state == Model1State.YELLOW:
                if elapsed >= M1_YELLOW_TIME:
                    self._transition_to(Model1State.RED)
                    continue

            elif self._state == Model1State.RED:
                if elapsed >= M1_RED_TIME:
                    self._transition_to(Model1State.GREEN)
                    continue

            time.sleep(LOOP_INTERVAL)

    # -----------------------------------------------------------------
    # Controle externo
    # -----------------------------------------------------------------

    def stop(self) -> None:
        """
        Para a execução da thread de forma graciosa.

        Desliga todos os LEDs após a parada.
        """
        self._running.clear()
        self.join(timeout=2.0)
        self._set_leds(green=False, yellow=False, red=False)
        print("[Modelo 1] Encerrado.")
