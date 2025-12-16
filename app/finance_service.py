# app/finance_service.py
from decimal import Decimal
from datetime import date
from app import db
from app.models import Transaction

class SessionFinanceService:
    """
    Serviço responsável por sincronizar as finanças de uma Sessão (Ensaio).
    Isola a lógica de manipulação de transações financeiras das rotas (Controllers).
    """

    @staticmethod
    def sync_transaction(session, should_exist, value, trans_type, category_key, desc_prefix, desc_full, use_date=None):
        """
        Sincroniza uma única transação vinculada a uma sessão.
        - Se deve existir (should_exist=True) e não existe: Cria.
        - Se existe: Atualiza valores.
        - Se não deve existir (should_exist=False) mas existe: Deleta.
        - Utiliza a coluna 'category' para identificação precisa (Novo padrão).
        - Fallback para 'startswith' description (Padrão legado).
        """
        if use_date is None:
            use_date = date.today()

        # Busca a transação existente
        # 1. Tenta achar pela categoria oficial (Padrão Novo)
        managed_trans = next((t for t in session.transactions if t.category == category_key), None)
        
        # 2. Fallback: Tenta achar pelo padrão antigo de texto (Legado) se não achou pela categoria
        # Isso garante a migração suave dos dados antigos sem scripts SQL manuais
        if not managed_trans and desc_prefix:
            managed_trans = next((t for t in session.transactions if (not t.category) and t.description and t.description.startswith(desc_prefix)), None)
        
        # Validações de segurança
        final_value = value if value is not None else Decimal('0.00')
        
        if should_exist and final_value > 0:
            if managed_trans:
                # Atualiza transação existente (Lazy Migration de categoria inclusa)
                managed_trans.value = final_value
                managed_trans.transaction_date = use_date
                if not managed_trans.category:
                    managed_trans.category = category_key 
            else:
                # Cria nova transação
                new_trans = Transaction(
                    description=desc_full,
                    transaction_type=trans_type,
                    value=final_value,
                    transaction_date=use_date,
                    session_id=session.id,
                    category=category_key,
                    status='efetivado' # Padrão para sessões que são pagas no ato ou confirmadas
                )
                db.session.add(new_trans)
        
        elif managed_trans:
            # Se foi desmarcado ou o valor zerou, remove a transação existente
            db.session.delete(managed_trans)

    @staticmethod
    def update_session_financials(session, form):
        """
        Orquestra a atualização de todas as categorias financeiras de um ensaio.
        """
        # Cálculos auxiliares (Regra de Negócio)
        remaining_value = form.total_value.data - form.down_payment.data
        extra_photos_value = (Decimal(form.extra_photos_qty.data or 0) * form.extra_photo_unit_price.data)
        printing_value = (Decimal(form.printing_qty.data or 0) * form.printing_unit_price.data)
        
        # 1. Entrada
        SessionFinanceService.sync_transaction(
            session=session,
            should_exist=form.down_payment_paid.data,
            value=form.down_payment.data,
            trans_type='entry',
            category_key='session_down_payment',
            desc_prefix='Entrada ensaio',
            desc_full=f"Entrada ensaio ({session.type.name}): {session.session_code}",
            use_date=form.session_date.data
        )
        
        # 2. Pagamento Final
        # A regra aqui diz: se o valor restante for zero, não gera transação final (lógica 'paid')
        should_exist_final = form.total_value_paid.data and remaining_value > 0
        SessionFinanceService.sync_transaction(
            session=session,
            should_exist=should_exist_final,
            value=remaining_value,
            trans_type='entry',
            category_key='session_settlement',
            desc_prefix='Pag. final ensaio',
            desc_full=f"Pag. final ensaio: {session.session_code}",
            use_date=form.session_date.data
        )

        # 3. Fotos Extras
        SessionFinanceService.sync_transaction(
            session=session,
            should_exist=form.extra_photos_paid.data,
            value=extra_photos_value,
            trans_type='entry',
            category_key='session_extra_photos',
            desc_prefix='Fotos extras ensaio',
            desc_full=f"Fotos extras ensaio: {session.session_code}",
            use_date=form.session_date.data
        )

        # 4. Impressões
        SessionFinanceService.sync_transaction(
            session=session,
            should_exist=form.printing_paid.data,
            value=printing_value,
            trans_type='entry',
            category_key='session_printing',
            desc_prefix='Impressões ensaio',
            desc_full=f"Impressões ensaio: {session.session_code}",
            use_date=form.session_date.data
        )

        # 5. Custo
        cost_exists = bool(session.session_cost and session.session_cost > 0)
        SessionFinanceService.sync_transaction(
            session=session,
            should_exist=cost_exists,
            value=session.session_cost,
            trans_type='exit',
            category_key='session_cost',
            desc_prefix='Custo ensaio',
            desc_full=f"Custo ensaio: {session.session_code}",
            use_date=form.session_date.data
        )