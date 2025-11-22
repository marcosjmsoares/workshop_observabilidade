from datetime import datetime, UTC
from pydantic import BaseModel
import requests
from sqlalchemy import create_engine, Column, String, Integer, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from time import sleep
import logfire  # Adicionar


# Configurar Logfire ANTES de tudo
logfire.configure()  # Isso autentica e configura o Logfire


# URL da API para buscar o valor atual do Bitcoin
URL = 'https://api.coinbase.com/v2/prices/spot?currency=USD'


# Configuração do banco de dados PostgreSQL remoto
POSTGRES_URI = "postgresql://postgres_kafka_workshop_wpd2_user:9bj0Uz1eLtY9L8SlSa5pYBtfgIn3kRsT@dpg-d4ec2kqli9vc73aq76m0-a.oregon-postgres.render.com/postgres_kafka_workshop_wpd2"


# Base declarativa do SQLAlchemy
Base = declarative_base()


# Modelo da tabela ANTES de create_all
class BitcoinDataModel(Base):
    __tablename__ = "bitcoin_data"
    id = Column(Integer, primary_key=True, autoincrement=True)
    amount = Column(String, nullable=False)
    base = Column(String, nullable=False)
    currency = Column(String, nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(UTC))


# Configurar a engine globalmente
engine = create_engine(POSTGRES_URI, echo=False)

# Instrumentar SQLAlchemy para Logfire
logfire.instrument_sqlalchemy(engine=engine)  # Adicionar essa linha

Base.metadata.create_all(engine)
print("Tabelas criadas (se não existiam).")


# Configurar a sessão do SQLAlchemy
Session = sessionmaker(bind=engine)


# Modelo Pydantic para validação de dados
class BitcoinData(BaseModel):
    amount: str
    base: str
    currency: str


class ApiResponse(BaseModel):
    data: BitcoinData


def test_connection():
    """Testa a conexão com o banco PostgreSQL."""
    try:
        with engine.connect() as conn:
            logfire.info("Conexão bem-sucedida com o PostgreSQL!")
    except Exception as e:
        logfire.error(f"Erro ao conectar ao banco de dados: {e}")


def extract():
    """Faz uma requisição à API para obter o valor do Bitcoin."""
    with logfire.span("extract_bitcoin_data"):  # Adicionar span
        response = requests.get(url=URL)
        logfire.info("Dados extraídos da API", response=response.json())
        return response.json()


def transform(data):
    """Valida os dados recebidos da API usando os modelos Pydantic."""
    with logfire.span("transform_bitcoin_data"):  # Adicionar span
        validated_data = ApiResponse(**data)
        logfire.info("Dados validados", data=validated_data.model_dump())
        return validated_data.model_dump()


def load(data):
    """Carrega os dados validados para um banco de dados PostgreSQL remoto."""
    with logfire.span("load_to_postgres"):  # Adicionar span
        session = Session()

        bitcoin_entry = BitcoinDataModel(
            amount=data['data']['amount'],
            base=data['data']['base'],
            currency=data['data']['currency'],
            timestamp=datetime.now(UTC)
        )

        session.add(bitcoin_entry)
        session.commit()
        
        logfire.info("Dados inseridos no PostgreSQL", 
                    amount=bitcoin_entry.amount, 
                    base=bitcoin_entry.base)

        results = session.query(BitcoinDataModel).all()
        logfire.info(f"Total de registros no banco: {len(results)}")

        session.close()


# Loop contínuo do pipeline ETL
logfire.info("Iniciando o loop do pipeline ETL")
try:
    while True:
        with logfire.span("etl_pipeline_iteration"):  # Span para toda a iteração
            logfire.info("Executando o pipeline ETL...")
            raw_data = extract()
            transformed_data = transform(raw_data)
            load(transformed_data)
            logfire.info("Pipeline concluído. Aguardando 10 segundos...")
            sleep(10)
except KeyboardInterrupt:
    logfire.warn("Execução interrompida pelo usuário")
