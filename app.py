from flask import Flask, jsonify, request
from flask_cors import CORS
import cloudscraper
import re
import time
import traceback

app = Flask(__name__)
CORS(app, origins="*")

def fazer_requisicao(scraper, url, params=None, headers=None, tentativas=3):
    for i in range(tentativas):
        try:
            response = scraper.get(url, params=params, headers=headers)
            if response.status_code == 200:
                return response
            print(f"Tentativa {i+1}: status {response.status_code}")
            time.sleep(2)
        except Exception as e:
            print(f"Tentativa {i+1} erro: {e}")
            time.sleep(2)
    return None

@app.route("/saldo", methods=["GET", "OPTIONS"])
def consultar_saldo():
    if request.method == "OPTIONS":
        response = jsonify({})
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Headers", "*")
        response.headers.add("Access-Control-Allow-Methods", "GET, OPTIONS")
        return response, 200

    cpf = request.args.get("cpf")

    if not cpf:
        return jsonify({"erro": "CPF não informado"}), 400

    try:
        scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'android',
                'mobile': True
            }
        )

        headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 11; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Referer": "https://www.sitpass.com.br/",
            "Accept-Language": "pt-BR,pt;q=0.9"
        }

        url_cartao = f"https://www.sitpass.com.br/servicosonline/consultasaldo/cartoes?cpf={cpf}"
        print(f"Buscando cartao para CPF: {cpf}")
        response_cartao = fazer_requisicao(scraper, url_cartao, headers=headers)

        if not response_cartao:
            print("Falhou ao buscar cartao")
            return jsonify({"erro": "Serviço indisponível, tente novamente"}), 503

        print(f"Status cartao: {response_cartao.status_code}")

        cartaoId        = re.search(r'value="([^"]+)"\s*name="cartaoId"',        response_cartao.text)
        crdsnr          = re.search(r'value="([^"]+)"\s*name="crdsnr"',          response_cartao.text)
        cartaoNumero    = re.search(r'value="([^"]+)"\s*name="cartaoNumero"',     response_cartao.text)
        cartaoDescricao = re.search(r'value="([^"]+)"\s*name="cartaoDescricao"', response_cartao.text)
        tipoParceria    = re.search(r'value="([^"]+)"\s*name="tipoParceria"',     response_cartao.text)

        if not cartaoId:
            print("CartaoId nao encontrado no HTML")
            print("HTML recebido (primeiros 500 chars):", response_cartao.text[:500])
            return jsonify({"erro": "Cartão não encontrado para este CPF"}), 404

        url_saldo = "https://www.sitpass.com.br/servicosonline/consultasaldo/cartoes/saldo"
        params = {
            "cpf":             cpf,
            "cpfMascara":      "",
            "tipoParceria":    tipoParceria.group(1),
            "cartaoId":        cartaoId.group(1),
            "crdsnr":          crdsnr.group(1),
            "cartaoDesignId":  "6",
            "cartaoDescricao": cartaoDescricao.group(1),
            "cartaoNumero":    cartaoNumero.group(1)
        }

        print("Buscando saldo...")
        response_saldo = fazer_requisicao(scraper, url_saldo, params=params, headers=headers)

        if not response_saldo:
            print("Falhou ao buscar saldo")
            return jsonify({"erro": "Serviço indisponível, tente novamente"}), 503

        match = re.search(r'R\$\s*([\d,.]+)', response_saldo.text)

        if match:
            print(f"Saldo encontrado: {match.group(1)}")
            response = jsonify({
                "cpf":             cpf,
                "cartaoNumero":    cartaoNumero.group(1),
                "cartaoDescricao": cartaoDescricao.group(1),
                "saldo":           match.group(1),
                "saldo_formatado": f"R$ {match.group(1)}"
            })
            response.headers.add("Access-Control-Allow-Origin", "*")
            return response
        else:
            print("Saldo nao encontrado no HTML")
            print("HTML saldo (primeiros 500 chars):", response_saldo.text[:500])
            return jsonify({"erro": "Saldo não encontrado"}), 404

    except Exception as e:
        print("ERRO COMPLETO:")
        print(traceback.format_exc())
        return jsonify({"erro": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
