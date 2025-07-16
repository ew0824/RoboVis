import math
from pathlib import Path
from vuer import Vuer
from vuer.schemas import DefaultScene, Urdf, Movable

# Get the path to the external Vuer client_build directory
client_build_path = Path(__file__).parent.parent.parent / "external" / "vuer" / "vuer" / "client_build"

app = Vuer(
    host="0.0.0.0",
    port=8012,
    static_root="assets/urdf/eoat_7",
    # Override the client_root to point to the external Vuer client_build
    client_root=client_build_path,
    # Add query parameters to configure the frontend
    queries=dict(
        reconnect=True,
        collapseMenu=True,
    ),
)

@app.spawn(start=True)
async def main(session):
    session.set @ DefaultScene(
        Movable(
            Urdf(
                src="http://localhost:8012/static/urdf/eoat/eoat.urdf",
                jointValues={},
                key="robot"
            ),
            position=[0, 0, 0.3],
            rotation=[0, math.pi, math.pi],
            scale=2.0,
        ),
        grid=True,
    )

if __name__ == "__main__":
    app.run()