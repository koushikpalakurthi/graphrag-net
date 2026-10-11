"""
Stage 2b: Train a GNN on the CTI knowledge graph to produce learned node
embeddings, rather than relying solely on symbolic traversal (per the paper's
Stage 2 spec).

Architecture: heterogeneous GraphSAGE (HeteroConv wrapping SAGEConv per
relation type) -- chosen because the graph is genuinely heterogeneous (11
node types, 13 relation types) and SAGEConv's neighbor-sampling design scales
better than a full R-GCN basis decomposition for a graph this size, while
still being relation-aware via HeteroConv's per-edge-type convolution.

Training objective: self-supervised link prediction (per the methodology --
"train self-supervised first ... since you likely lack labeled downstream
data initially"). For each real edge, the model scores it against a
corrupted negative (same source, random destination of the same node type)
and is trained to rank the real edge higher via BCE-with-logits.

Edges are made undirected (T.ToUndirected) before training so message
passing flows both ways -- e.g. a ThreatGroup's embedding should be
influenced by which Techniques it uses, and vice versa.
"""
import sys
import pickle
from pathlib import Path

import torch
import torch.nn.functional as F
import torch_geometric.transforms as T
from torch_geometric.nn import HeteroConv, SAGEConv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import PROCESSED_DIR

HIDDEN_DIM = 128
EMBED_DIM = 64
NUM_EPOCHS = 100
LEARNING_RATE = 0.005
SEED = 42

torch.manual_seed(SEED)


class HeteroGraphSAGE(torch.nn.Module):
    """Two-layer heterogeneous GraphSAGE encoder, one output vector per node."""

    def __init__(self, edge_types, hidden_dim, embed_dim):
        super().__init__()
        self.conv1 = HeteroConv(
            {et: SAGEConv((-1, -1), hidden_dim) for et in edge_types},
            aggr="sum",
        )
        self.conv2 = HeteroConv(
            {et: SAGEConv((-1, -1), embed_dim) for et in edge_types},
            aggr="sum",
        )

    def forward(self, x_dict, edge_index_dict):
        x_dict = self.conv1(x_dict, edge_index_dict)
        x_dict = {k: F.relu(v) for k, v in x_dict.items()}
        x_dict = self.conv2(x_dict, edge_index_dict)
        return x_dict


def sample_negative_edges(edge_index, num_nodes_dst, num_samples):
    """Corrupt the destination endpoint with a random node of the same type."""
    src = edge_index[0]
    neg_dst = torch.randint(0, num_nodes_dst, (num_samples,))
    idx = torch.randint(0, src.size(0), (num_samples,))
    return src[idx], neg_dst


def link_prediction_loss(z_dict, edge_index_dict, orig_edge_types):
    """
    BCE loss over positive (real) vs negative (corrupted-destination) edges,
    computed only on the original (non-reversed) relation types -- the
    reverse edges added by ToUndirected are for message passing only, not
    separate supervision signal, to avoid double-counting each real edge.
    """
    total_loss = 0.0
    n_terms = 0
    for et in orig_edge_types:
        src_type, rel, dst_type = et
        edge_index = edge_index_dict[et]
        if edge_index.size(1) == 0:
            continue

        z_src, z_dst = z_dict[src_type], z_dict[dst_type]

        pos_src, pos_dst = edge_index[0], edge_index[1]
        pos_score = (z_src[pos_src] * z_dst[pos_dst]).sum(dim=-1)

        neg_src, neg_dst = sample_negative_edges(edge_index, z_dst.size(0), pos_src.size(0))
        neg_score = (z_src[neg_src] * z_dst[neg_dst]).sum(dim=-1)

        scores = torch.cat([pos_score, neg_score])
        labels = torch.cat([torch.ones_like(pos_score), torch.zeros_like(neg_score)])
        total_loss += F.binary_cross_entropy_with_logits(scores, labels)
        n_terms += 1

    return total_loss / max(n_terms, 1)


def main():
    graph_path = PROCESSED_DIR / "hetero_graph.pt"
    if not graph_path.exists():
        raise FileNotFoundError(f"{graph_path} not found -- run build_pyg_graph.py first.")

    data = torch.load(graph_path, weights_only=False)
    orig_edge_types = list(data.edge_types)  # capture before ToUndirected adds reverse types

    # Keep node_ids aside (ToUndirected + model forward don't need them, and
    # non-tensor attributes can trip up some PyG transforms).
    node_ids_by_type = {nt: data[nt].node_ids for nt in data.node_types}
    for nt in data.node_types:
        del data[nt].node_ids

    data = T.ToUndirected()(data)
    print(f"After ToUndirected: {len(data.edge_types)} relation types "
          f"({len(orig_edge_types)} original + reverse)")

    model = HeteroGraphSAGE(data.edge_types, HIDDEN_DIM, EMBED_DIM)
    optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)

    # Lazy SAGEConv layers need one forward pass to infer input dims before
    # the optimizer can see real parameter shapes.
    with torch.no_grad():
        model(data.x_dict, data.edge_index_dict)
    optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)

    print(f"\nTraining HeteroGraphSAGE: hidden={HIDDEN_DIM}, embed={EMBED_DIM}, "
          f"epochs={NUM_EPOCHS}\n")

    model.train()
    for epoch in range(1, NUM_EPOCHS + 1):
        optimizer.zero_grad()
        z_dict = model(data.x_dict, data.edge_index_dict)
        loss = link_prediction_loss(z_dict, data.edge_index_dict, orig_edge_types)
        loss.backward()
        optimizer.step()
        if epoch == 1 or epoch % 10 == 0:
            print(f"  epoch {epoch:3d}/{NUM_EPOCHS}  link-prediction loss: {loss.item():.4f}")

    # Final embeddings, keyed back to real entity ids for Stage 2c validation.
    model.eval()
    with torch.no_grad():
        z_dict = model(data.x_dict, data.edge_index_dict)

    embeddings = {}
    for node_type, z in z_dict.items():
        ids = node_ids_by_type[node_type]
        for i, node_id in enumerate(ids):
            embeddings[node_id] = z[i].numpy()

    out_path = PROCESSED_DIR / "node_embeddings.pkl"
    with open(out_path, "wb") as f:
        pickle.dump(embeddings, f)

    torch.save(model.state_dict(), PROCESSED_DIR / "gnn_model.pt")

    print(f"\nSaved {len(embeddings)} node embeddings -> {out_path}")
    print(f"Saved trained model weights -> {PROCESSED_DIR / 'gnn_model.pt'}")


if __name__ == "__main__":
    main()
