import math
from vuer import Vuer
from vuer.schemas import DefaultScene, Urdf, Movable

app = Vuer(
    host="0.0.0.0",
    port=8012,
    static_root="assets/urdf/eoat_7",
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