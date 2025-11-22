import logfire

logfire.configure()

logfire.info('Hello, {name}!', name='world')
logfire.warn('esse é um aviso')
logfire.error('esse é um erro')
