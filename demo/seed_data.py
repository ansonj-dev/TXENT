from __future__ import annotations

import textwrap
from typing import Any

import httpx


API_BASE = "http://localhost:8000"


DOCUMENTS = [
    {
        "source": "network_theory.txt",
        "text": """
        Information spreads through social networks because every person, account, or institution can be modeled as a node connected by edges of attention, trust, and repeated interaction. A message rarely moves evenly across the whole network. It passes through clusters, pauses at weak ties, and accelerates when a highly connected hub repeats it. Threshold activation is one of the most important mechanisms. A person may ignore a claim after hearing it once, but after three friends, a news channel, and a familiar creator all mention it, the perceived risk of sharing drops. Echo chambers strengthen this effect because the same signal returns through many paths and starts to feel like independent confirmation. Viral cascades begin when enough adjacent nodes activate in a short period, creating a burst of reposts that platforms may further amplify through ranking systems. Dense communities preserve messages, while bridges carry them between groups. The structure of the graph therefore matters as much as the content of the message. A rumor can fail in a sparse network even if it is emotionally compelling, while a plain update can travel far when it enters a cluster with many overlapping edges. Hubs accelerate diffusion, but they also create vulnerabilities because correcting a false claim often requires reaching the same hubs or finding alternative bridges around them. Modern social platforms add another layer through recommendation algorithms that infer similarity and push content across invisible edges. This can create long-range shortcuts where a message leaps from one local community to another. The result is a propagation system that resembles contagion, wildfire, and threshold cascades at the same time: local exposure changes individual behavior, and aggregated behavior changes the global network state.
        """,
    },
    {
        "source": "climate_systems.txt",
        "text": """
        Climate systems are shaped by feedback loops that can either stabilize a condition or amplify a disturbance. Ice-albedo feedback is a clear example. Bright ice reflects incoming solar radiation, but when warming melts sea ice, darker ocean water absorbs more heat. That extra absorption causes more melting, which exposes more dark water and reinforces the original warming. The carbon cycle contains similar amplification pathways. Permafrost stores ancient organic material, and when frozen ground thaws, microbes decompose that material and release carbon dioxide and methane. Methane traps heat strongly, so the release contributes to additional warming and deeper thaw. Forest stress, wildfire, ocean circulation, and cloud formation all interact in nonlinear ways. A tipping point occurs when gradual pressure pushes the system past a threshold where internal feedbacks begin driving change without the same external forcing. This does not mean every change is instant, but it does mean the previous balance is no longer reliable. Ocean circulation can shift when freshwater from melting ice changes salinity and density gradients. Coral reefs can move from living ecosystems to algae-dominated states after repeated heat stress. The climate record shows that complex systems can remain stable for long periods and then reorganize quickly when reinforcing loops align. Scientists study these dynamics with observations, paleoclimate evidence, and models that represent energy flows, reservoirs, and delays. Delays are important because the effects of today's emissions continue unfolding over decades. Nonlinear behavior makes policy timing crucial. Intervening before feedbacks strengthen is easier than reversing a cascade after it becomes self-sustaining. Climate risk is therefore not only a question of average temperature. It is a question of connected feedback loops, thresholds, and the resilience of the systems that support stable human and ecological life.
        """,
    },
    {
        "source": "ml_optimization.txt",
        "text": """
        Machine learning optimization is the process of moving through a loss landscape to find parameters that make a model perform well. Gradient descent estimates the direction of steepest improvement by computing derivatives of the loss with respect to model weights. A learning rate controls the size of each step. If the learning rate is too large, training can bounce around or diverge; if it is too small, convergence may be painfully slow. Real neural network loss landscapes contain valleys, saddle points, flat regions, sharp basins, and local minima. The goal is not always to find a perfect global optimum, but to find a solution that generalizes well to unseen data. Adam and related optimizers adapt step sizes using running estimates of gradient moments, which often improves training stability. Learning rate schedules reduce the step size over time so early training explores broadly while later training settles into a useful region. Hyperparameter search expands the optimization problem beyond weights to include batch size, regularization strength, architecture choices, and data augmentation policy. Constraints matter because training time, memory, energy, and available data limit what can be explored. Good optimization balances exploitation of promising regions with enough exploration to avoid poor basins. Regularization changes the geometry by penalizing overly complex solutions, while normalization can smooth the path through parameter space. Convergence is measured with training loss, validation metrics, and sometimes calibration or robustness tests. In large models, distributed training adds communication constraints, gradient noise, mixed precision behavior, and checkpoint strategy. Optimization theory gives language for all of these tradeoffs: objective functions, constraints, search spaces, gradients, curvature, and stopping criteria. A successful training run is a coordinated search through a high-dimensional space where each step uses local information to approach a model that behaves well globally.
        """,
    },
    {
        "source": "urban_planning.txt",
        "text": """
        Urban systems are hierarchical because cities must organize many layers of activity at different scales. A metropolitan region contains districts, districts contain neighborhoods, neighborhoods contain blocks, and blocks contain buildings, streets, utilities, and public spaces. Planning decisions at one level shape possibilities at the levels below. Zoning can separate industrial, residential, commercial, and mixed-use areas, while transportation networks connect those areas through roads, rail, buses, bike lanes, and pedestrian corridors. Infrastructure layers include water, power, drainage, waste, broadband, emergency access, and public health services. These layers are not independent. Density gradients influence transit demand, and transit access influences where density can grow. Neighborhood classification helps planners compare places by land use, income, mobility, environmental exposure, and access to schools or parks. A central business district may have high job density and vertical construction, while outer neighborhoods may have lower density and more car dependence. Good spatial organization recognizes parent-child relationships: a bus stop serves a corridor, a corridor serves a neighborhood, and a network of corridors serves the whole city. Cities also evolve over time. A new rail line can reorganize development patterns, while flood risk can force changes in zoning and infrastructure investment. Informal activity complicates the hierarchy because real communities often use space in ways that official maps do not capture. Effective planning therefore combines formal structure with observed behavior. The city is a nested system of systems, where governance, physical networks, economic flows, and social identity must be coordinated across levels. Understanding the hierarchy makes it easier to find bottlenecks, protect resilience, and design interventions that improve daily life without breaking the relationships that make neighborhoods work.
        """,
    },
    {
        "source": "epidemiology.txt",
        "text": """
        Disease propagation depends on contact patterns, biological infectiousness, immunity, and the timing of interventions. Epidemiologists often describe spread with the reproduction number R0, which estimates how many secondary infections one infectious person would cause in a fully susceptible population. If R0 is above one, cases can grow; if it is below one, the outbreak tends to shrink. SIR models divide the population into susceptible, infectious, and recovered groups, then use equations to represent movement between those states. Real epidemics are more complex because people are not mixed uniformly. Households, schools, workplaces, transit systems, hospitals, and social events create networks where some individuals have many more contacts than others. Superspreading events can produce sudden jumps in case counts, especially for pathogens that transmit efficiently indoors or before symptoms appear. Herd immunity reduces spread when enough people are immune through vaccination or prior infection, making transmission chains less likely to continue. Contact tracing attempts to find exposed people quickly so they can isolate before infecting others. Intervention timing is critical. Early action can prevent exponential growth, while delayed action may require stronger measures because each generation of cases seeds the next. Masks, ventilation, testing, vaccination, travel guidance, and temporary gathering limits all change the effective reproduction number by reducing transmission opportunities. Mathematical models help compare scenarios, but their reliability depends on assumptions about behavior, reporting, variant properties, and immunity duration. Epidemic spread is therefore both a network propagation problem and a public health coordination problem. The same pathogen can fade in one community and surge in another if contact structure, immunity, and response differ. Understanding thresholds, delays, and feedback between behavior and risk perception is essential for controlling outbreaks.
        """,
    },
]


QUERIES = [
    "How do epidemics spread through populations?",
    "What causes climate tipping points?",
    "How is information organized in hierarchical systems?",
]


def post_json(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    with httpx.Client(timeout=120.0) as client:
        response = client.post(f"{API_BASE}{path}", json=payload)
        response.raise_for_status()
        return response.json()


def main() -> None:
    print("Seeding TXENT demo memory")
    for document in DOCUMENTS:
        text = textwrap.dedent(document["text"]).strip()
        result = post_json("/ingest", {"text": text, "source": document["source"]})
        print(f"Ingested {document['source']}: {result['chunks_ingested']} chunks")

    print("\nQuery checks")
    for query in QUERIES:
        result = post_json("/retrieve", {"query": query, "generate_answer": False})
        schema = result["l3_structural"][0]["name"] if result["l3_structural"] else "none"
        kick = result["kick"]
        top_l1 = result["l1_surface"][0]["text"][:180] if result["l1_surface"] else "none"
        print(f"\nQuery: {query}")
        print(f"L3 schema: {schema}")
        print(f"Kick: fired={kick['fired']} severity={kick['severity']} divergence={kick['divergence']}")
        print(f"Top L1: {top_l1}")


if __name__ == "__main__":
    main()
