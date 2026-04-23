"""
traffic_light_model2.py — Máquina de estados do Modelo 2 (Cruzamento Completo).

Controla um cruzamento completo via código de 3 bits enviado pela GPIO.
Sequência obrigatória: 1 → 2 → 4 → 5 → 6 → 4 → 1 ...

Interpretação dos códigos:
  1: Via principal VERDE   / Via cruzamento VERMELHO
  2: Via principal AMARELO / Via cruzamento VERMELHO
  4: TUDO VERMELHO (segurança)
  5: Via cruzamento VERDE  / Via principal VERMELHO
  6: Via cruzamento AMARELO / Via principal VERMELHO

Botões de pedestre:
  - Botão Principal (GPIO 25): solicita abertura da travessia na via principal.
    → Se o sinal da via principal está verde, antecipa mudança para amarelo (S1 → S2).
  - Botão Cruzamento (GPIO 22): solicita abertura da travessia na via de cruzamento.
    → Se o sinal da via de cruzamento está verde, antecipa mudança para amarelo (S5 → S6).

Tempos mínimos e máximos são respeitados antes de aceitar antecipação.
"""

import threading
import time
from enum import Enum

from src.config import (
    LOOP_INTERVAL,
    M2_ALL_RED_TIME,
    M2_CROSS_GREEN_MAX,
    M2_CROSS_GREEN_MIN,
    M2_GPIO_BIT0,
    M2_GPIO_BIT1,
    M2_GPIO_BIT2,
    M2_GPIO_BTN_CRUZAMENTO,
    M2_GPIO_BTN_PRINCIPAL,
    M2_MAIN_GREEN_MAX,
    M2_MAIN_GREEN_MIN,
    M2_YELLOW_TIME,
)
from src.gpio_module import GPIOController


class Model2State(Enum):
    """
    Estados da máquina de estados do Modelo 2.

    O estado 4 (tudo vermelho) aparece duas vezes no ciclo:
      - S4_ALL_RED_A: após o amarelo da via principal (transição 2 → 4)
      - S4_ALL_RED_B: após o amarelo da via de cruzamento (transição 6 → 4)

    Ambos enviam código GPIO = 4, mas são estados internos distintos para
    permitir transições lineares na FSM sem lógica condicional.
    """

    S1_MAIN_GREEN = "S1_PRINCIPAL_VERDE"
    S2_MAIN_YELLOW = "S2_PRINCIPAL_AMARELO"
    S4_ALL_RED_A = "S4_TUDO_VERMELHO_A"
    S5_CROSS_GREEN = "S5_CRUZAMENTO_VERDE"
    S6_CROSS_YELLOW = "S6_CRUZAMENTO_AMARELO"
    S4_ALL_RED_B = "S4_TUDO_VERMELHO_B"


# Mapeamento estado → código de 3 bits para o GPIO
_STATE_TO_GPIO_CODE: dict[Model2State, int] = {
    Model2State.S1_MAIN_GREEN: 1,
    Model2State.S2_MAIN_YELLOW: 2,
    Model2State.S4_ALL_RED_A: 4,
    Model2State.S5_CROSS_GREEN: 5,
    Model2State.S6_CROSS_YELLOW: 6,
    Model2State.S4_ALL_RED_B: 4,
}

# Nomes legíveis para impressão no terminal
_STATE_DISPLAY_NAME: dict[Model2State, str] = {
    Model2State.S1_MAIN_GREEN: "Principal VERDE / Cruzamento VERMELHO (código 1)",
    Model2State.S2_MAIN_YELLOW: "Principal AMARELO (código 2)",
    Model2State.S4_ALL_RED_A: "TUDO VERMELHO (código 4)",
    Model2State.S5_CROSS_GREEN: "Cruzamento VERDE / Principal VERMELHO (código 5)",
    Model2State.S6_CROSS_YELLOW: "Cruzamento AMARELO (código 6)",
    Model2State.S4_ALL_RED_B: "TUDO VERMELHO (código 4)",
}


class TrafficLightModel2(threading.Thread):
    """
    Cruzamento completo controlado por código de 3 bits.

    Roda em thread própria. O loop principal verifica a cada LOOP_INTERVAL
    se é hora de transicionar de estado, considerando tempos mínimos/máximos
    e pedidos de pedestre.
    """

    def __init__(self, gpio: GPIOController):
        """
        Inicializa o semáforo Modelo 2.

        Args:
            gpio: Instância compartilhada do controlador GPIO.
        """
        super().__init__(daemon=True, name="Model2-Thread")
        self._gpio = gpio
        self._running = threading.Event()

        # Flags de pedestre (independentes por via)
        self._ped_main_requested = threading.Event()    # Botão principal (GPIO 25)
        self._ped_cross_requested = threading.Event()   # Botão cruzamento (GPIO 22)

        # Estado inicial
        self._state = Model2State.S1_MAIN_GREEN
        self._state_start: float = 0.0

        # Pinos de saída (3 bits)
        self._output_pins = (M2_GPIO_BIT0, M2_GPIO_BIT1, M2_GPIO_BIT2)
        for pin in self._output_pins:
            self._gpio.setup_output(pin)

        # Pinos de entrada (botões)
        self._gpio.setup_input(M2_GPIO_BTN_PRINCIPAL)
        self._gpio.setup_input(M2_GPIO_BTN_CRUZAMENTO)

        # Registrar callbacks de botão com debounce
        self._gpio.register_callback(
            M2_GPIO_BTN_PRINCIPAL, self._on_button_principal
        )
        self._gpio.register_callback(
            M2_GPIO_BTN_CRUZAMENTO, self._on_button_cruzamento
        )

    # -----------------------------------------------------------------
    # Callbacks de botão
    # -----------------------------------------------------------------

    def _on_button_principal(self, channel: int) -> None:
        """
        Callback do botão de pedestre principal (GPIO 25).

        Solicita abertura da travessia na via principal.
        Efeito: se o sinal da via principal está verde (S1),
        antecipa a mudança para amarelo (S2).
        """
        print(f"[Modelo 2] Botão pedestre principal acionado (GPIO {channel})", flush=True)
        self._ped_main_requested.set()

    def _on_button_cruzamento(self, channel: int) -> None:
        """
        Callback do botão de pedestre cruzamento (GPIO 22).

        Solicita abertura da travessia na via de cruzamento.
        Efeito: se o sinal da via de cruzamento está verde (S5),
        antecipa a mudança para amarelo (S6).
        """
        print(f"[Modelo 2] Botão pedestre cruzamento acionado (GPIO {channel})", flush=True)
        self._ped_cross_requested.set()

    # -----------------------------------------------------------------
    # Controle GPIO
    # -----------------------------------------------------------------

    def _apply_state(self) -> None:
        """Envia o código de 3 bits correspondente ao estado atual."""
        code = _STATE_TO_GPIO_CODE[self._state]
        self._gpio.write_3bit(self._output_pins, code)

    # -----------------------------------------------------------------
    # Transição de estados
    # -----------------------------------------------------------------

    def _transition_to(self, new_state: Model2State) -> None:
        """
        Realiza a transição para um novo estado.

        Imprime a mudança no terminal, atualiza o GPIO e reseta o
        timestamp. As flags de pedestre são resetadas apenas quando
        o estado correspondente é concluído.

        Args:
            new_state: Próximo estado da FSM.
        """
        old_display = _STATE_DISPLAY_NAME[self._state]
        new_display = _STATE_DISPLAY_NAME[new_state]
        print(f"[Modelo 2] {old_display} → {new_display}", flush=True)

        self._state = new_state
        self._state_start = time.monotonic()
        self._apply_state()

    # -----------------------------------------------------------------
    # Loop principal da FSM
    # -----------------------------------------------------------------

    def run(self) -> None:
        """
        Loop principal da thread — executa a máquina de estados.

        Sequência: S1 → S2 → S4_A → S5 → S6 → S4_B → S1 ...

        A cada iteração (LOOP_INTERVAL ≈ 50ms):
          1. Calcula o tempo decorrido no estado atual.
          2. Verifica condições de transição (tempo mín/máx + botão).
          3. Dorme pelo intervalo configurado.
        """
        self._running.set()
        self._state_start = time.monotonic()
        self._apply_state()
        print(
            f"[Modelo 2] Iniciado no estado "
            f"{_STATE_DISPLAY_NAME[self._state]}",
            flush=True,
        )

        while self._running.is_set():
            elapsed = time.monotonic() - self._state_start

            if self._state == Model2State.S1_MAIN_GREEN:
                # -------------------------------------------------------
                # Via principal VERDE (código 1)
                # Tempo: min 10s, max 20s
                # Botão principal (GPIO 25) antecipa (após tempo mínimo)
                # -------------------------------------------------------
                if self._ped_main_requested.is_set():
                    if elapsed >= M2_MAIN_GREEN_MIN:
                        self._ped_main_requested.clear()
                        self._transition_to(Model2State.S2_MAIN_YELLOW)
                        continue

                if elapsed >= M2_MAIN_GREEN_MAX:
                    self._ped_main_requested.clear()
                    self._transition_to(Model2State.S2_MAIN_YELLOW)
                    continue

            elif self._state == Model2State.S2_MAIN_YELLOW:
                # -------------------------------------------------------
                # Via principal AMARELO (código 2)
                # Tempo fixo: 2s
                # -------------------------------------------------------
                if elapsed >= M2_YELLOW_TIME:
                    self._transition_to(Model2State.S4_ALL_RED_A)
                    continue

            elif self._state == Model2State.S4_ALL_RED_A:
                # -------------------------------------------------------
                # TUDO VERMELHO após principal (código 4)
                # Tempo fixo: 2s
                # -------------------------------------------------------
                if elapsed >= M2_ALL_RED_TIME:
                    self._transition_to(Model2State.S5_CROSS_GREEN)
                    continue

            elif self._state == Model2State.S5_CROSS_GREEN:
                # -------------------------------------------------------
                # Via cruzamento VERDE (código 5)
                # Tempo: min 5s, max 10s
                # Botão cruzamento (GPIO 22) antecipa (após tempo mínimo)
                # -------------------------------------------------------
                if self._ped_cross_requested.is_set():
                    if elapsed >= M2_CROSS_GREEN_MIN:
                        self._ped_cross_requested.clear()
                        self._transition_to(Model2State.S6_CROSS_YELLOW)
                        continue

                if elapsed >= M2_CROSS_GREEN_MAX:
                    self._ped_cross_requested.clear()
                    self._transition_to(Model2State.S6_CROSS_YELLOW)
                    continue

            elif self._state == Model2State.S6_CROSS_YELLOW:
                # -------------------------------------------------------
                # Via cruzamento AMARELO (código 6)
                # Tempo fixo: 2s
                # -------------------------------------------------------
                if elapsed >= M2_YELLOW_TIME:
                    self._transition_to(Model2State.S4_ALL_RED_B)
                    continue

            elif self._state == Model2State.S4_ALL_RED_B:
                # -------------------------------------------------------
                # TUDO VERMELHO após cruzamento (código 4)
                # Tempo fixo: 2s
                # -------------------------------------------------------
                if elapsed >= M2_ALL_RED_TIME:
                    self._transition_to(Model2State.S1_MAIN_GREEN)
                    continue

            time.sleep(LOOP_INTERVAL)

    # -----------------------------------------------------------------
    # Controle externo
    # -----------------------------------------------------------------

    def stop(self) -> None:
        """
        Para a execução da thread de forma graciosa.

        Envia código 4 (tudo vermelho) como estado seguro ao encerrar.
        """
        self._running.clear()
        self.join(timeout=2.0)
        # Estado seguro: tudo vermelho
        self._gpio.write_3bit(self._output_pins, 4)
        print("[Modelo 2] Encerrado.", flush=True)
