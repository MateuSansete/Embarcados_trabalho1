"""
gpio_module.py — Módulo de abstração da GPIO para Raspberry Pi.

Encapsula toda a interação com RPi.GPIO, provendo:
  - Configuração de pinos (entrada/saída)
  - Leitura e escrita individual
  - Escrita de código de 3 bits (para Modelo 2)
  - Registro de callbacks com debounce por interrupção (borda de subida)
  - Limpeza segura dos recursos
"""

import RPi.GPIO as GPIO

from src.config import DEBOUNCE_MS


class GPIOController:
    """
    Controlador centralizado de GPIO.

    Usa numeração BCM e mantém registro dos pinos configurados
    para garantir limpeza adequada ao encerrar.
    """

    def __init__(self):
        """Inicializa o GPIO no modo BCM com warnings desabilitados."""
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        self._configured_pins: list[int] = []

    # -----------------------------------------------------------------
    # Configuração de pinos
    # -----------------------------------------------------------------

    def setup_output(self, pin: int, initial: int = GPIO.LOW) -> None:
        """
        Configura um pino como saída digital.

        Args:
            pin: Número BCM do pino.
            initial: Estado inicial (GPIO.LOW ou GPIO.HIGH).
        """
        GPIO.setup(pin, GPIO.OUT, initial=initial)
        self._configured_pins.append(pin)

    def setup_input(self, pin: int, pull_down: bool = True) -> None:
        """
        Configura um pino como entrada digital.

        Args:
            pin: Número BCM do pino.
            pull_down: Se True, ativa pull-down interno (padrão para botões
                       normalmente em baixa).
        """
        pud = GPIO.PUD_DOWN if pull_down else GPIO.PUD_UP
        GPIO.setup(pin, GPIO.IN, pull_up_down=pud)
        self._configured_pins.append(pin)

    # -----------------------------------------------------------------
    # Leitura e escrita
    # -----------------------------------------------------------------

    def write(self, pin: int, value: bool) -> None:
        """
        Escreve um valor digital em um pino de saída.

        Args:
            pin: Número BCM do pino.
            value: True para HIGH, False para LOW.
        """
        GPIO.output(pin, GPIO.HIGH if value else GPIO.LOW)

    def read(self, pin: int) -> bool:
        """
        Lê o valor digital de um pino de entrada (polling).

        Args:
            pin: Número BCM do pino.

        Returns:
            True se HIGH, False se LOW.
        """
        return bool(GPIO.input(pin))

    def write_3bit(self, pins: tuple[int, int, int], code: int) -> None:
        """
        Escreve um código de 3 bits em três pinos de saída.

        O código é decomposto bit a bit:
          - pins[0] recebe bit 0 (LSB)
          - pins[1] recebe bit 1
          - pins[2] recebe bit 2 (MSB)

        Args:
            pins: Tupla (bit0_pin, bit1_pin, bit2_pin).
            code: Valor inteiro de 0 a 7.

        Raises:
            ValueError: Se code não está no intervalo [0, 7].
        """
        if not 0 <= code <= 7:
            raise ValueError(f"Código deve estar entre 0 e 7, recebido: {code}")

        for i, pin in enumerate(pins):
            bit_value = bool((code >> i) & 1)
            self.write(pin, bit_value)

    # -----------------------------------------------------------------
    # Interrupções (callbacks com debounce)
    # -----------------------------------------------------------------

    def register_callback(
        self,
        pin: int,
        callback,
        debounce_ms: int = DEBOUNCE_MS,
    ) -> None:
        """
        Registra um callback para borda de subida com debounce.

        O debounce é tratado pelo parâmetro `bouncetime` do RPi.GPIO,
        que ignora bordas adicionais dentro da janela especificada.
        Isso evita busy-waiting e garante tratamento por interrupção.

        Args:
            pin: Número BCM do pino de entrada.
            callback: Função a ser chamada (recebe o pino como argumento).
            debounce_ms: Janela de debounce em milissegundos.
        """
        GPIO.add_event_detect(
            pin,
            GPIO.RISING,
            callback=callback,
            bouncetime=debounce_ms,
        )

    # -----------------------------------------------------------------
    # Limpeza
    # -----------------------------------------------------------------

    def cleanup(self) -> None:
        """
        Libera todos os recursos GPIO configurados.

        Deve ser chamado ao encerrar o programa para deixar os pinos
        em estado seguro (alta impedância).
        """
        GPIO.cleanup()
        self._configured_pins.clear()
