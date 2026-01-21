from jinja2 import Template

template_str = """
{% if 'Parcial' in (item.status or '') or (item.pontuacao|float > 0 and item.pontuacao|float < area.pontuacao_maxima_item|default(10)|float) %}
<span class="badge bg-warning">Parcialmente Conforme</span>
{% else %}
<span class="badge bg-danger">Não Conforme</span>
{% endif %}
"""

# Case 1: Status explícito "Parcialmente Conforme"
item_1 = {
    "status": "Parcialmente Conforme",
    "observacao": "Teste",
    # pontuacao missing (None/Undefined)
}

# Case 2: Pontuação Parcial (sem status ou status None)
item_2 = {
    "status": None,
    "pontuacao": 5.0
}

# Case 3: Não Conforme explícito
item_3 = {
    "status": "Não Conforme",
    "pontuacao": 0
}

# Case 4: Status OPEN (Fallback)
item_4 = {
    "status": "OPEN",
    "pontuacao": 0
}

area = {"pontuacao_maxima_item": 10}

t = Template(template_str)

print("--- Case 1: Status Parcial ---")
print(t.render(item=item_1, area=area))

print("\n--- Case 2: Pontuação Parcial ---")
print(t.render(item=item_2, area=area))

print("\n--- Case 3: Não Conforme ---")
print(t.render(item=item_3, area=area))

print("\n--- Case 4: OPEN ---")
print(t.render(item=item_4, area=area))
