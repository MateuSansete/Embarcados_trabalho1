"""
config.py — Constantes de configuração do sistema de semáforos.

Centraliza todos os pinos GPIO, tempos de cada estado e parâmetros
de debounce para os dois modelos de semáforo.
"""

# =============================================================================
# Modelo 1 — Semáforo Simples (3 LEDs individuais, Cruzamento 1)
# =============================================================================

# Pinos GPIO de saída (LEDs)
M1_GPIO_GREEN = 17   # LED Verde
M1_GPIO_YELLOW = 18  # LED Amarelo
M1_GPIO_RED = 23     # LED Vermelho

# Pinos GPIO de entrada (Botões de pedestre)
M1_GPIO_BTN_PRINCIPAL = 1    # Botão pedestre principal
M1_GPIO_BTN_CRUZAMENTO = 12  # Botão pedestre cruzamento

# Temporização do Modelo 1 (em segundos)
M1_GREEN_TIME = 10    # Duração total do verde
M1_YELLOW_TIME = 2    # Duração do amarelo
M1_RED_TIME = 10      # Duração do vermelho
M1_GREEN_MIN_TIME = 5  # Tempo mínimo de verde antes de aceitar botão

# =============================================================================
# Modelo 2 — Cruzamento Completo (código de 3 bits, Cruzamento 2)
# =============================================================================

# Pinos GPIO de saída (3 bits do código do semáforo)
M2_GPIO_BIT0 = 24  # Bit 0 (LSB)
M2_GPIO_BIT1 = 8   # Bit 1
M2_GPIO_BIT2 = 7   # Bit 2 (MSB)

# Pinos GPIO de entrada (Botões de pedestre)
M2_GPIO_BTN_PRINCIPAL = 25   # Botão pedestre principal
M2_GPIO_BTN_CRUZAMENTO = 22  # Botão pedestre cruzamento

# Temporização do Modelo 2 (em segundos)
M2_MAIN_GREEN_MIN = 10    # Verde mínimo da via principal
M2_MAIN_GREEN_MAX = 20    # Verde máximo da via principal
M2_CROSS_GREEN_MIN = 5    # Verde mínimo da via de cruzamento
M2_CROSS_GREEN_MAX = 10   # Verde máximo da via de cruzamento
M2_YELLOW_TIME = 2        # Amarelo (ambas as vias)
M2_ALL_RED_TIME = 2       # Vermelho total (segurança)

# =============================================================================
# Parâmetros gerais
# =============================================================================

DEBOUNCE_MS = 200        # Debounce dos botões em milissegundos
LOOP_INTERVAL = 0.05     # Intervalo do loop principal (50ms) — granularidade da FSM
