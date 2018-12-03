from enum import Enum


def byte_to_hex(bytebuffer):
    return "".join(("%02x" % a) for a in bytebuffer)


# CASSSANDRA TYPES
class TxInputOutput(object):
    def __init__(self, address, value):
        self.address = address[0]
        self.value = value


class Value(object):
    def __init__(self, satoshi, eur, usd):
        self.satoshi = satoshi
        self.eur = round(eur, 2)
        self.usd = round(usd, 2)

    def __sub__(self, other):
        return Value(self.satoshi-other.satoshi, round(self.eur-other.eur, 2), round(self.usd-other.usd, 2))


class TxIdTime(object):
    def __init__(self, height, tx_hash, timestamp):
        self.height = height
        self.tx_hash = tx_hash
        self.timestamp = timestamp

    def serialize(self):
        return {
            "height": self.height,
            "tx_hash": self.tx_hash,
            "timestamp": self.timestamp,
        }


class AddressSummary(object):
    def __init__(self, total_received, total_spent):
        self.totalReceived = total_received
        self.totalSpent = total_spent


# CASSSANDRA TABLES
class ExchangeRate(object):
    def __init__(self, row):
        self.height = int(row.height.values[0])
        self.usd = int(row.usd.values[0])
        self.eur = int(row.eur.values[0])


class Statistics(object):
    def __init__(self, row):
        self.no_blocks = row.no_blocks
        self.no_address_relations = row.no_address_relations
        self.no_addresses = row.no_addresses
        self.no_clusters = row.no_clusters
        self.no_transactions = row.no_transactions
        self.timestamp = row.timestamp


class Tag(object):
    def __init__(self, row):
        self.address = row.address
        self.tag = row.tag
        self.tagUri = row.tag_uri
        self.description = row.description
        self.actorCategory = row.actor_category
        self.source = row.source
        self.sourceUri = row.source_uri
        self.timestamp = row.timestamp


class Transaction(object):
    def __init__(self, row, rates):
        self.txHash = byte_to_hex(row.tx_hash)
        self.coinbase = row.coinbase
        self.height = row.height
        if row.inputs:
            self.inputs = [TxInputOutput(input.address,
                                         Value(input.value,
                                               round(input.value*rates.eur*1e-8, 2),
                                               round(input.value*rates.usd*1e-8, 2)).__dict__).__dict__
                           for input in row.inputs]
        else:
            self.inputs = []
        self.outputs = [TxInputOutput(output.address, Value(output.value, round(output.value*rates.eur*1e-8, 2),
                                                            round(output.value*rates.usd*1e-8, 2)).__dict__).__dict__
                        for output in row.outputs if output.address]
        self.timestamp = row.timestamp
        self.totalInput = Value(row.total_input, round(row.total_input*rates.eur*1e-8, 2),
                                round(row.total_input*rates.usd*1e-8, 2)).__dict__
        self.totalOutput = Value(row.total_output, round(row.total_output*rates.eur*1e-8, 2),
                                 round(row.total_output*rates.usd*1e-8, 2)).__dict__


class BlockTransaction(object):
    def __init__(self, row, rates):
        self.txHash = byte_to_hex(row.tx_hash)
        self.noInputs = row.no_inputs
        self.noOutputs = row.no_outputs
        self.totalInput = Value(row.total_input, round(row.total_input*rates.eur*1e-8, 2), round(row.total_input*rates.usd*1e-8, 2)).__dict__
        self.totalOutput = Value(row.total_output, round(row.total_output*rates.eur*1e-8, 2),
                                 round(row.total_output*rates.usd*1e-8, 2)).__dict__


class Block(object):
    def __init__(self, row):
        self.height = row.height
        self.blockHash = byte_to_hex(row.block_hash)
        self.noTransactions = row.no_transactions
        self.timestamp = row.timestamp


class BlockWithTransactions(object):
    def __init__(self, row, rates):
        self.height = row.height
        self.txs = [BlockTransaction(tx, rates).__dict__ for tx in row.txs]


class Address(object):
    def __init__(self, row, exchange_rate):
        self.address_prefix = row.address_prefix
        self.address = row.address
        self.firstTx = TxIdTime(row.first_tx.height, byte_to_hex(row.first_tx.tx_hash), row.first_tx.timestamp).__dict__
        self.lastTx = TxIdTime(row.last_tx.height, byte_to_hex(row.last_tx.tx_hash), row.last_tx.timestamp).__dict__
        self.noIncomingTxs = row.no_incoming_txs
        self.noOutgoingTxs = row.no_outgoing_txs
        received = Value(row.total_received.satoshi, round(row.total_received.eur, 2), round(row.total_received.usd, 2))
        self.totalReceived = received.__dict__
        spent = Value(row.total_spent.satoshi, round(row.total_spent.eur, 2), round(row.total_spent.usd, 2))
        self.totalSpent = spent.__dict__
        balance = compute_balance(row.total_received.satoshi, row.total_spent.satoshi, exchange_rate)
        self.balance = balance.__dict__
        self.inDegree = row.in_degree
        self.outDegree = row.out_degree


def compute_balance(total_received_satoshi, total_spent_satoshi, exchange_rate):
    balance_satoshi = total_received_satoshi - total_spent_satoshi
    balance = Value(balance_satoshi, round(balance_satoshi*exchange_rate.eur*1e-8, 2),
                    round(balance_satoshi*exchange_rate.usd*1e-8, 2))
    return balance


class AddressTransactions(object):
    def __init__(self, row, rates):
        self.address = row.address
        self.address_prefix = row.address_prefix
        self.txHash = byte_to_hex(row.tx_hash)
        self.value = Value(row.value, round(row.value*rates.eur*1e-8, 2), round(row.value*rates.usd*1e-8, 2)).__dict__
        self.height = row.height
        self.timestamp = row.timestamp
        self.txIndex = row.tx_index


class Cluster(object):
    def __init__(self, row, exchange_rate):
        self.cluster = int(row.cluster)
        self.firstTx = TxIdTime(row.first_tx.height, byte_to_hex(row.first_tx.tx_hash), row.first_tx.timestamp).__dict__
        self.lastTx = TxIdTime(row.last_tx.height, byte_to_hex(row.last_tx.tx_hash), row.last_tx.timestamp).__dict__
        self.noAddresses = row.no_addresses
        self.noIncomingTxs = row.no_incoming_txs
        self.noOutgoingTxs = row.no_outgoing_txs
        received = Value(row.total_received.satoshi, round(row.total_received.eur, 2), round(row.total_received.usd, 2))
        self.totalReceived = received.__dict__
        spent = Value(row.total_spent.satoshi, round(row.total_spent.eur, 2), round(row.total_spent.usd, 2))
        self.totalSpent = spent.__dict__
        balance = compute_balance(row.total_received.satoshi, row.total_spent.satoshi, exchange_rate)
        self.balance = balance.__dict__
        self.inDegree = row.in_degree
        self.outDegree = row.out_degree


class AddressIncomingRelations(object):
    def __init__(self, row):
        self.dstAddressPrefix = row.dst_address_prefix
        self.dstAddress = row.dst_address
        self.srcCategory = Category(row.src_category)
        self.estimatedValue = Value(row.estimated_value.satoshi, round(row.estimated_value.eur, 2), round(row.estimated_value.usd, 2)).__dict__
        self.srcAddress = row.src_address
        self.noTransactions = row.no_transactions
        self.srcProperties = AddressSummary(row.src_properties.total_received, row.src_properties.total_spent)

    def id(self):
        return self.srcAddress

    def toJsonNode(self):
        node = {"id": self.id(),
                "nodeType": "address",
                "received": self.srcProperties.totalReceived,
                "balance": self.srcProperties.totalReceived - self.srcProperties.totalSpent,  # satoshi
                "category": self.srcCategory.name}
        return node

    def toJsonEdge(self):
        edge = {"source": self.srcAddress,
                "target": self.dstAddress,
                "transactions": self.noTransactions,
                "estimatedValue": self.estimatedValue}
        return edge
    def toJson(self):
        return {
            "id" : self.id(),
            "nodeType" : "address",
            "category" : self.srcCategory.name,
            "received" : self.srcProperties.totalReceived,
            "balance" : self.srcProperties.totalReceived - self.srcProperties.totalSpent,  # satoshi
            "noTransactions" : self.noTransactions,
            "estimatedValue" : self.estimatedValue
        }


class AddressOutgoingRelations(object):
    def __init__(self, row):
        self.srcAddressPrefix = row.src_address_prefix
        self.srcAddress = row.src_address
        self.dstCategory = Category(row.dst_category)
        self.estimatedValue = Value(row.estimated_value.satoshi, round(row.estimated_value.eur, 2), round(row.estimated_value.usd, 2)).__dict__
        self.dstAddress = row.dst_address
        self.noTransactions = row.no_transactions
        self.dstProperties = AddressSummary(row.dst_properties.total_received, row.dst_properties.total_spent)

    def id(self):
        return self.dstAddress

    def toJsonNode(self):
        node = {"id": self.id(),
                "nodeType": "address",
                "received": self.dstProperties.totalReceived,
                "balance": (self.dstProperties.totalReceived - self.dstProperties.totalSpent),  # satoshi
                "category": self.dstCategory.name}
        return node

    def toJsonEdge(self):
        edge = {"source": self.srcAddress,
                "target": self.dstAddress,
                "transactions": self.noTransactions,
                "estimatedValue": self.estimatedValue}
        return edge
    def toJson(self):
        return {
            "id" : self.id(),
            "nodeType" : 'address',
            "category" : self.dstCategory.name,
            "received" : self.dstProperties.totalReceived,
            "balance" : self.dstProperties.totalReceived - self.dstProperties.totalSpent,  # satoshi
            "noTransactions" : self.noTransactions,
            "estimatedValue" : self.estimatedValue
        }


class ClusterSummary(object):
    def __init__(self, no_addresses, total_received, total_spent):
        self.noAddresses = no_addresses
        self.totalReceived = total_received
        self.totalSpent = total_spent


class ClusterIncomingRelations(object):
    def __init__(self, row):
        self.dstCluster = str(row.dst_cluster)
        self.srcCluster = str(row.src_cluster)
        self.srcCategory = Category(row.src_category)
        self.srcProperties = ClusterSummary(row.src_properties.no_addresses, row.src_properties.total_received, row.src_properties.total_spent)
        self.value = Value(row.value.satoshi, round(row.value.eur, 2), round(row.value.usd, 2)).__dict__
        self.noTransactions = row.no_transactions

    def id(self):
        return self.srcCluster

    def toJsonNode(self):
        node = {"id": self.id(),
                "nodeType": "cluster" if self.id().isdigit() else "address",
                "received": self.srcProperties.totalReceived,
                "balance": self.srcProperties.totalReceived - self.srcProperties.totalSpent,  # satoshi
                "category": self.srcCategory.name}
        return node

    def toJsonEdge(self):
        edge = {"source": self.srcCluster,
                "target": self.dstCluster,
                "transactions": self.noTransactions,
                "estimatedValue": self.value}
        return edge
    def toJson(self):
        return {
            "id" : self.id(),
            "nodeType" : "cluster" if self.id().isdigit() else 'address',
            "category" : self.srcCategory.name,
            "received" : self.srcProperties.totalReceived,
            "balance" : self.srcProperties.totalReceived - self.srcProperties.totalSpent,  # satoshi
            "noTransactions" : self.noTransactions,
            "estimatedValue" : self.value
        }


class ClusterOutgoingRelations(object):
    def __init__(self, row):
        self.srcCluster = str(row.src_cluster)
        self.dstCluster = str(row.dst_cluster)
        self.dstCategory = Category(row.dst_category)
        self.dstProperties = ClusterSummary(row.dst_properties.no_addresses, row.dst_properties.total_received, row.dst_properties.total_spent)
        self.value = Value(row.value.satoshi, round(row.value.eur, 2), round(row.value.usd, 2)).__dict__
        self.noTransactions = row.no_transactions

    def id(self):
        return self.dstCluster

    def toJsonNode(self):
        node = {"id": self.id(),
                "nodeType": "cluster" if self.id().isdigit() else "address",
                "received": self.dstProperties.totalReceived,
                "balance": self.dstProperties.totalReceived - self.dstProperties.totalSpent,  # satoshi
                "category": self.dstCategory.name}
        return node

    def toJsonEdge(self):
        edge = {"source": self.srcCluster,
                "target": self.dstCluster,
                "transactions": self.noTransactions,
                "estimatedValue": self.value}
        return edge
    def toJson(self):
        return {
            "id" : self.id(),
            "nodeType" : "cluster" if self.id().isdigit() else 'address',
            "category" : self.dstCategory.name,
            "received" : self.dstProperties.totalReceived,
            "balance" : self.dstProperties.totalReceived - self.dstProperties.totalSpent,  # satoshi
            "noTransactions" : self.noTransactions,
            "estimatedValue" : self.value
        }


class Category(Enum):
    Unknown = 0
    Implicit = 1
    Explicit = 2
    Manual = 3


class AddressEgoNet(object):
    def __init__(self, focus_address, explicit_tags, implicit_tags, incoming_relations, outgoing_relations):
        self.focusAddress = focus_address
        self.explicitTags = explicit_tags
        self.implicitTags = implicit_tags
        self.incomingRelations = incoming_relations
        self.outgoingRelations = outgoing_relations
        if self.explicitTags:
            self.focusNodeCategory = Category.Explicit
        else:
            if self.implicitTags:
                self.focusNodeCategory = Category.Implicit
            else:
                self.focusNodeCategory = Category.Unknown

        self.focusNode = [{"id": self.focusAddress.address,
                           "nodeType": "address",
                           "received": self.focusAddress.totalReceived["satoshi"],
                           "balance": self.focusAddress.totalReceived["satoshi"] - self.focusAddress.totalSpent["satoshi"],
                           "category": self.focusNodeCategory.name
                           }]

    # receives a List[EgonetRelation]
    def dedupNodes(self, addrRelations):
        dedupNodes = {relation.id(): relation for relation in addrRelations}
        return dedupNodes.values()

    def construct(self, address, direction):
        nodes = []
        if "in" in direction:
            nodes.extend(self.focusNode)
            eNodes = [node.toJsonNode() for node in self.dedupNodes(self.incomingRelations)]
            nodes.extend(eNodes)
        else:
            if "out" in direction:
                nodes.extend(self.focusNode)
                eNodes = [node.toJsonNode() for node in self.dedupNodes(self.outgoingRelations)]
                nodes.extend(eNodes)
            else:
                nodes.extend(self.focusNode)
                eNodes = [node.toJsonNode() for node in self.dedupNodes(self.incomingRelations)]
                nodes.extend(eNodes)
                eNodes = [node.toJsonNode() for node in self.dedupNodes(self.outgoingRelations)]
                nodes.extend(eNodes)
        nodes = [dict(t) for t in {tuple(d.items()) for d in nodes}]  # remove duplicate nodes

        edges = []
        if "in" in direction:
            new = [edge.toJsonEdge() for edge in self.incomingRelations]
            edges.extend(new)
        else:
            if "out" in direction:
                new = [edge.toJsonEdge() for edge in self.outgoingRelations]
                edges.extend(new)
            else:
                new = [edge.toJsonEdge() for edge in self.incomingRelations]
                edges.extend(new)
                new = [edge.toJsonEdge() for edge in self.outgoingRelations]
                edges.extend(new)

        ret = {"focusNode": address, "nodes": nodes, "edges": edges}
        return ret


class ClusterEgoNet(object):
    def __init__(self, focusCluster, clusterTags, incomingRelations, outgoingRelations):
        self.focusCluster = focusCluster
        self.clusterTags = clusterTags
        self.incomingRelations = incomingRelations
        self.outgoingRelations = outgoingRelations

        if clusterTags:
            self.focusNodeCategory = Category.Explicit
        else:
            self.focusNodeCategory = Category.Unknown

        self.focusNode = [{
            "id": self.focusCluster.cluster,
            "nodeType": "cluster",
            "received": self.focusCluster.totalReceived["satoshi"],
            "balance": self.focusCluster.totalReceived["satoshi"] - self.focusCluster.totalSpent["satoshi"],
            "category":self.focusNodeCategory.name
        }]

    def dedupNodes(self, clusterRelations):
        dedupNodes = {relation.id(): relation for relation in clusterRelations}
        return dedupNodes.values()

    def construct(self, cluster, direction):
        nodes = []
        nodes.extend(self.focusNode)
        if "in" in direction:
            new = [node.toJsonNode() for node in self.dedupNodes(self.incomingRelations)]
            nodes.extend(new)
        else:
            if "out" in direction:
                new = [node.toJsonNode() for node in self.dedupNodes(self.outgoingRelations)]
                nodes.extend(new)
            else:
                new = [node.toJsonNode() for node in self.dedupNodes(self.incomingRelations)]
                nodes.extend(new)
                new = [node.toJsonNode() for node in self.dedupNodes(self.outgoingRelations)]
                nodes.extend(new)
        nodes = [dict(t) for t in {tuple(d.items()) for d in nodes}]  # remove duplicate nodes

        edges = []
        if "in" in direction:
            new = [edge.toJsonEdge() for edge in self.incomingRelations]
            edges.extend(new)
        else:
            if "out" in direction:
                new = [edge.toJsonEdge() for edge in self.outgoingRelations]
                edges.extend(new)
            else:
                new = [edge.toJsonEdge() for edge in self.incomingRelations]
                edges.extend(new)
                new = [edge.toJsonEdge() for edge in self.outgoingRelations]
                edges.extend(new)
        ret = {"focusNode": cluster, "nodes": nodes, "edges": edges}
        return ret


class ClusterAddresses(object):
    def __init__(self, row, exchange_rate):
        self.cluster = str(row.cluster)
        self.address = row.address
        self.noIncomingTxs = row.no_incoming_txs
        self.noOutgoingTxs = row.no_outgoing_txs
        self.firstTx = TxIdTime(row.first_tx.height, byte_to_hex(row.first_tx.tx_hash), row.first_tx.timestamp).__dict__
        self.lastTx = TxIdTime(row.last_tx.height, byte_to_hex(row.last_tx.tx_hash), row.last_tx.timestamp).__dict__
        totalReceived = Value(row.total_received.satoshi, round(row.total_received.eur, 2), round(row.total_received.usd, 2))
        self.totalReceived = totalReceived.__dict__
        totalSpent = Value(row.total_spent.satoshi, round(row.total_spent.eur, 2), round(row.total_spent.usd, 2))
        self.totalSpent = totalSpent.__dict__
        balance = compute_balance(row.total_received.satoshi, row.total_spent.satoshi, exchange_rate)
        self.balance = balance.__dict__
