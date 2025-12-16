# app/fields.py
from wtforms import StringField
from wtforms.widgets import TextInput
from decimal import Decimal, InvalidOperation
import re

class CurrencyInput(TextInput):
    """Widget customizado para inputs de moeda."""
    def __call__(self, field, **kwargs):
        kwargs.setdefault('class', 'form-control currency-input')
        
        # Renderiza o valor puro (ex: "1250.50") no data-value para o Javascript ler
        if isinstance(field.data, (float, int, Decimal)):
            kwargs['data-value'] = f"{field.data:.2f}"
        elif field.data is None:
            kwargs['data-value'] = "0.00"
        else:
            kwargs['data-value'] = str(field.data)
            
        kwargs['value'] = '' 
        
        return super().__call__(field, **kwargs)

class CurrencyField(StringField):
    """
    Campo customizado para valores de moeda.
    Entrada: String formatada (R$ 1.000,00) via formulário.
    Saída: Objeto Decimal (precisão financeira) para o modelo.
    """
    widget = CurrencyInput()

    def process_data(self, value):
        # Recebe o valor do modelo (Decimal) e guarda
        self.data = value if value is not None else Decimal('0.00')

    def process_formdata(self, valuelist):
        # Processa a string vinda do request (ex: "R$ 1.234,50")
        if valuelist and valuelist[0]:
            raw_value = valuelist[0]
            try:
                # 1. Remove tudo que não for dígito ou vírgula (separador decimal BR)
                # Isso evita injeção de lixo e simplifica o parsing
                clean_str = re.sub(r'[^\d,]', '', raw_value)
                
                # 2. Troca vírgula por ponto para conversão padrão do Python
                decimal_str = clean_str.replace(',', '.')
                
                # 3. Converte para Decimal para manter precisão financeira
                self.data = Decimal(decimal_str)
            except (ValueError, InvalidOperation):
                self.data = Decimal('0.00')
        else:
            self.data = Decimal('0.00')