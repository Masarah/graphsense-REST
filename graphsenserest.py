# https://datastax.github.io/python-driver/
# https://speakerdeck.com/mitsuhiko/advanced-flask-patterns-1

# https://github.com/TerbiumLabs/flask-cassandra/blob/master/flask_cassandra.py
# https://github.com/tiangolo/uwsgi-nginx-flask-docker

from flask import Flask, jsonify, request, g, abort
from flask_cors import CORS
from graphsensedao import *

app = Flask(__name__)

CORS(app)
app.config.from_object(__name__)
app.config.update(dict(
    SECRET_KEY='development key',
    CASSANDRA_NODES=['spark1', 'spark2'],
    MAPPING={\
        'btc': 'btc_blocksci_transformed_20181123',
        'btc_raw': 'btc_blocksci_raw',
        'bch': 'bch_blocksci_transformed_20181115',
        'bch_raw': 'bch_blocksci_raw',
        'ltc': 'ltc_blocksci_transformed_20181126',
        'ltc_raw': 'ltc_blocksci_raw',
    }
))
app.config.from_envvar('GRAPHSENSE_REST_SETTINGS', silent=True)
currency_mapping = app.config['MAPPING']


@app.route('/')
def index():
    statistics = dict()
    for currency in currency_mapping.keys():
        if len(currency.split('_')) == 1:
            statistics[currency] = query_statistics(currency)
    return jsonify(statistics)

@app.route('/<currency>/exchangerates')
def exchange_rates(currency):
    manual_limit = 100000
    limit = request.args.get('limit')
    offset = request.args.get('offset')
    if offset and not isinstance(offset, int):
        abort(404, 'Invalid offset')
    if limit and (not isinstance(offset, int) or limit > manual_limit):
        abort(404, 'Invalid limit')

    exchange_rates = query_exchange_rates(currency, offset, limit)
    return jsonify({
        "exchangeRates": exchange_rates
    })

@app.route('/<currency>/block/<int:height>')
def block(currency, height):
    block = query_block(currency, height)
    if not block:
        abort(404, "Block height %d not found" % height)
    return jsonify(block)

@app.route('/<currency>/block/<int:height>/transactions')
def block_transactions(currency, height):
    block_transactions = query_block_transactions(currency, height)
    if not block_transactions:
        abort(404, "Block height %d not found" % height)
    return jsonify(block_transactions)

@app.route('/<currency>/blocks')
def blocks(currency):
    page_state = request.args.get('page')
    (page_state, blocks) = query_blocks(currency, page_state)
    return jsonify({
        "nextPage": page_state.hex() if page_state is not None else None,
        "blocks": blocks
    })

@app.route('/<currency>/tx/<txHash>')
def transaction(currency, txHash):
    transaction = query_transaction(currency, txHash)
    if not transaction:
        abort(404, "Transaction id %s not found" % txHash)
    return jsonify(transaction)

@app.route('/<currency>/transactions')
def transactions(currency):
    page_state = request.args.get('page')
    (page_state, transactions) = query_transactions(currency, page_state)
    return jsonify({
        "nextPage": page_state.hex() if page_state is not None else None,
        "transactions": transactions
    })

@app.route('/<currency>/search')
def search(currency):
    expression = request.args.get('q')
    if not expression:
        abort(404, "Expression parameter not provided")
    leading_zeros = 0
    pos = 0
    # leading zeros will be lost when casting to int
    while expression[pos] == '0':
        pos += 1
        leading_zeros +=1
    limit = request.args.get('limit')
    if not limit:
        limit = 50
    else:
        try:
            limit = int(limit)
        except:
            abort(404, 'Invalid limit value')
    if len(expression) >= 5:
        prefix = expression[:5]
    else:
        prefix = expression  # this will return an empty list because the user did not input enough chars
    transactions = query_transaction_search(currency, prefix)  # no limit here, else we miss the specified transaction
    addresses = query_address_search(currency, prefix)  # no limit here, else we miss the specified address
    return jsonify({
        'addresses': [row.address for row in addresses.current_rows if row.address.startswith(expression)][:limit],
        'transactions': [tx for tx in ['0'*leading_zeros + str(hex(int.from_bytes(row.tx_hash, byteorder='big')))[2:]\
                                       for row in transactions.current_rows] if tx.startswith(expression)][:limit]
    })

@app.route('/<currency>/address/<address>')
def address(currency, address):
    if not address:
        abort(404, "Address not provided")

    result = query_address(currency, address)
    return jsonify(result.__dict__) if result else jsonify({})

@app.route('/<currency>/address_with_tags/<address>')
def address_with_tags(currency, address):
    if not address:
        abort(404, "Address not provided")

    result = query_address(currency, address)
    result.tags = query_address_tags(currency, address)
    return jsonify(result.__dict__) if result else jsonify({})

@app.route('/<currency>/address/<address>/transactions')
def address_transactions(currency, address):
    if not address:
        abort(404, "Address not provided")
    limit = request.args.get('limit')
    if limit is not None:
        try:
            limit = int(limit)
        except:
            abort(404, 'Invalid limit value')
    pagesize = request.args.get('pagesize')
    if pagesize is not None:
        try:
            pagesize = int(pagesize)
        except:
            abort(404, 'Invalid pagesize value')
    page_state = request.args.get('page')
    (page_state, rows) = query_address_transactions(currency, page_state, address, pagesize, limit)
    txs = [AddressTransactions(row, query_exchange_rate_for_height(currency, row.height)).__dict__ for row in rows]
    return jsonify({
        "nextPage": page_state.hex() if page_state is not None else None,
        "transactions": txs
    })

@app.route('/<currency>/address/<address>/tags')
def address_tags(currency, address):
    if not address:
        abort(404, "Address not provided")

    tags = query_address_tags(currency, address)
    return jsonify(tags)

@app.route('/<currency>/address/<address>/implicitTags')
def address_implicit_tags(currency, address):
    if not address:
        abort(404, "Address not provided")

    implicit_tags = query_implicit_tags(currency, address)
    return jsonify(implicit_tags)

@app.route('/<currency>/address/<address>/cluster')
def address_cluster(currency, address):
    if not address:
        abort(404, "Address not provided")

    address_cluster = query_address_cluster(currency, address)
    return jsonify(address_cluster)

@app.route('/<currency>/address/<address>/cluster_with_tags')
def address_cluster_with_tags(currency, address):
    if not address:
        abort(404, "Address not provided")

    address_cluster = query_address_cluster(currency, address)
    if 'cluster' in address_cluster:
        address_cluster['tags'] = query_cluster_tags(currency, address_cluster['cluster'])
    return jsonify(address_cluster)

@app.route('/<currency>/address/<address>/egonet')
def address_egonet(currency, address):
    direction = request.args.get('direction')
    if not direction:
        direction = ""

    limit = request.args.get('limit')
    if not limit:
        limit = 50
    else:
        limit = int(limit)
    try:
        _,incoming = query_address_incoming_relations(currency, None, address, None, int(limit))
        _,outgoing = query_address_outgoing_relations(currency, None, address, None, int(limit))
        egoNet = AddressEgoNet(
            query_address(currency, address),
            query_address_tags(currency, address),
            query_implicit_tags(currency, address),
            incoming,
            outgoing
        )
        ret = egoNet.construct(address, direction)
    except:
        ret = {}
    return jsonify(ret)

@app.route('/<currency>/address/<address>/neighbors')
def address_neighbors(currency, address):
    direction = request.args.get('direction')
    if not direction:
        abort(404, 'direction value missing')
    if 'in' in direction:
        isOutgoing = False
    elif 'out' in direction:
        isOutgoing = True
    else:
        abort(404, 'invalid direction value - has to be either in or out')
        

    limit = request.args.get('limit')
    if limit is not None:
        try:
            limit = int(limit)
        except:
            abort(404, 'Invalid limit value')

    pagesize = request.args.get('pagesize')
    if pagesize is not None:
        try:
            pagesize = int(pagesize)
        except:
            abort(404, 'Invalid pagesize value')
    page_state = request.args.get('page')
    if isOutgoing:
        (page_state, rows) = query_address_outgoing_relations(currency, page_state, address, pagesize, limit)
    else:
        (page_state, rows) = query_address_incoming_relations(currency, page_state, address, pagesize, limit)
    return jsonify({
        "nextPage": page_state.hex() if page_state is not None else None,
        "neighbors": [row.toJson() for row in rows]
    })

@app.route('/<currency>/cluster/<cluster>')
def cluster(currency, cluster):
    if not cluster:
        abort(404, "Cluster not provided")
    try:
        cluster = int(cluster)
    except:
        abort(404, "Invalid cluster ID")
    cluster_obj = query_cluster(currency, cluster)
    return jsonify(cluster_obj.__dict__) if cluster_obj else jsonify({})

@app.route('/<currency>/cluster_with_tags/<cluster>')
def cluster_with_tags(currency, cluster):
    if not cluster:
        abort(404, "Cluster id not provided")
    cluster_obj = query_cluster(currency, cluster)
    cluster_obj.tags = query_cluster_tags(currency, cluster)
    return jsonify(cluster_obj.__dict__) if cluster_obj else jsonify({})

@app.route('/<currency>/cluster/<cluster>/tags')
def cluster_tags(currency, cluster):
    if not cluster:
        abort(404, "Cluster not provided")
    try:
        cluster = int(cluster)
    except:
        abort(404, "Invalid cluster ID")
    tags = query_cluster_tags(currency, cluster)
    return jsonify(tags)

@app.route('/<currency>/cluster/<cluster>/addresses')
def cluster_addresses(currency, cluster):
    if not cluster:
        abort(404, "Cluster not provided")
    try:
        cluster = int(cluster)
    except:
        abort(404, "Invalid cluster ID")
    limit = request.args.get('limit')
    if limit is not None:
        try:
            limit = int(limit)
        except:
            abort(404, 'Invalid limit value')
    pagesize = request.args.get('pagesize')
    if pagesize is not None:
        try:
            pagesize = int(pagesize)
        except:
            abort(404, 'Invalid pagesize value')
    page = request.args.get('page')
    (page, addresses) = query_cluster_addresses(currency, cluster, page, pagesize, limit)
    return jsonify({
        "nextPage" : page.hex() if page is not None else None,
        "addresses" : addresses
        })


@app.route('/<currency>/cluster/<cluster>/egonet')
def cluster_egonet(currency, cluster):
    direction = request.args.get('direction')
    if not cluster:
        abort(404, "Cluster not provided")
    try:
        cluster = int(cluster)
        cluster = str(cluster)
    except:
        abort(404, "Invalid cluster ID")
    if not direction:
        direction = ""
    limit = request.args.get('limit')
    if not limit:
        limit = 50
    else:
        try:
            limit = int(limit)
        except:
            abort(404, 'Invalid limit value')
    try:
        egoNet = ClusterEgoNet(
            query_cluster(currency, cluster),
            query_cluster_tags(currency, cluster),
            query_cluster_incoming_relations(currency, cluster, int(limit)),
            query_cluster_outgoing_relations(currency, cluster, int(limit))
        )
        ret = egoNet.construct(cluster, direction)
    except:
        ret = {}
    return jsonify(ret)

@app.route('/<currency>/cluster/<cluster>/neighbors')
def cluster_neighbors(currency, cluster):
    direction = request.args.get('direction')
    if not direction:
        abort(404, 'direction value missing')
    if 'in' in direction:
        isOutgoing = False
    elif 'out' in direction:
        isOutgoing = True
    else:
        abort(404, 'invalid direction value - has to be either in or out')
        

    limit = request.args.get('limit')
    if limit is not None:
        try:
            limit = int(limit)
        except:
            abort(404, 'Invalid limit value')

    pagesize = request.args.get('pagesize')
    if pagesize is not None:
        try:
            pagesize = int(pagesize)
        except:
            abort(404, 'Invalid pagesize value')
    page_state = request.args.get('page')
    if isOutgoing:
        (page_state, rows) = query_cluster_outgoing_relations(currency, page_state, cluster, pagesize, limit)
    else:
        (page_state, rows) = query_cluster_incoming_relations(currency, page_state, cluster, pagesize, limit)
    return jsonify({
        "nextPage": page_state.hex() if page_state is not None else None,
        "neighbors": [row.toJson() for row in rows]
    })

@app.errorhandler(400)
def custom400(error):
    return jsonify({'message': error.description})

if __name__ == '__main__':
    connect(app)
    app.run(port=9000, debug=True, processes=1)

# @app.teardown_appcontext
# def cluster_shutdown(error):
#     """Shutdown all connections to cassandra."""
#     app.logger.debug("Shutting down Cassandra cluster.")
#     app.cluster.shutdown()
