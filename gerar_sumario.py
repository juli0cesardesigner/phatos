import os

# Lista exata de arquivos baseada na nova arquitetura PhatosApp (v2.0)
files_to_read = [
    'run.py',
    'app/fields.py',
    'app/finance_service.py',
    'app/forms.py',
    'app/models.py',
    'app/__init__.py',
    'app/blueprints/auth.py',
    'app/blueprints/config.py',
    'app/blueprints/crm.py',
    'app/blueprints/finance.py',
    'app/blueprints/goals.py',
    'app/blueprints/kanban.py',
    'app/blueprints/reports.py',
    'app/blueprints/sessions.py',
    'app/static/css/custom.css',
    'app/templates/429.html',
    'app/templates/add_edit_client.html',
    'app/templates/add_edit_goal.html',
    'app/templates/add_edit_session_type.html',
    'app/templates/add_session.html',
    'app/templates/add_transaction.html',
    'app/templates/base.html',
    'app/templates/clients.html',
    'app/templates/client_details.html',
    'app/templates/edit_session.html',
    'app/templates/edit_transaction.html',
    'app/templates/financeiro.html',
    'app/templates/goal_details.html',
    'app/templates/index.html',
    'app/templates/kanban.html',
    'app/templates/login.html',
    'app/templates/metas.html',
    'app/templates/pricing.html',
    'app/templates/register.html',
    'app/templates/reports.html',
    'app/templates/report_lead_source.html',
    'app/templates/report_profitability.html',
    'app/templates/session_types.html',
    'app/templates/sessoes.html'
]

output_file = 'sumario_projeto.txt'

def generate_summary():
    print("Iniciando geração do sumário do PhatosApp v2.0...")
    with open(output_file, 'w', encoding='utf-8') as outfile:
        outfile.write(f"--- SUMÁRIO COMPLETO DE CÓDIGO DO PROJETO ---\n")
        outfile.write(f"--- STATUS: v2.0 Stable (Secure, Decimal, Service Layer) ---\n\n")
        
        count = 0
        for file_path in files_to_read:
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as infile:
                        outfile.write(f"--- INÍCIO DO ARQUIVO: {file_path} ---\n\n")
                        outfile.write(infile.read())
                        outfile.write(f"\n\n--- FIM DO ARQUIVO: {file_path} ---\n\n")
                        print(f"[OK] Processado: {file_path}")
                        count += 1
                except Exception as e:
                    print(f"[ERRO] Falha ao ler {file_path}: {e}")
                    outfile.write(f"--- ERRO AO LER O ARQUIVO: {file_path} ---\n\n")
            else:
                print(f"[AVISO] Arquivo não encontrado: {file_path}")

    print(f"\nProcesso concluído! {count} arquivos processados.")
    print(f"O sumário foi salvo em: {os.path.abspath(output_file)}")
    print("-" * 50)

if __name__ == '__main__':
    generate_summary()