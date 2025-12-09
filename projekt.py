import os
import geopandas as gpd
from flask import Flask, jsonify, request
from flask_cors import CORS
from math import radians, sin, cos, sqrt, atan2

app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
STATIONS_PATH = os.path.join(DATA_DIR, "stations.sqlite")
LINES_PATH = os.path.join(DATA_DIR, "railway.sqlite")


@app.route("/")
def home():
    return {"status": "API działa poprawnie :)"}



def load_stations_gdf():
    gdf = gpd.read_file(STATIONS_PATH, layer="stations").reset_index(drop=True)
    return gdf



@app.route("/stations_list")
def stations_list():
    try:
        gdf = load_stations_gdf()
        records = []
        for uid, row in gdf.reset_index().iterrows():
            geom = row.geometry
            if geom is None or geom.is_empty:
                continue
            lon = float(geom.x)
            lat = float(geom.y)
            records.append({
                "uid": int(uid),
                "name": row.get("name") or row.get("nazwa") or f"station_{uid}",
                "lon": lon,
                "lat": lat
            })
        return jsonify(records)
    except Exception as e:
        return {"error": str(e)}, 500



def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0  # km
    phi1 = radians(lat1)
    phi2 = radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)

    a = sin(dphi / 2.0) ** 2 + cos(phi1) * cos(phi2) * sin(dlambda / 2.0) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c



@app.route("/nearest")
def nearest():
    try:
        lat = float(request.args.get("lat"))
        lon = float(request.args.get("lon"))
    except Exception:
        return {"error": "Podaj poprawne parametry lat i lon (np. ?lat=51.1&lon=17.03)"}, 400

    n = request.args.get("n", default=5, type=int)
    try:
        gdf = load_stations_gdf()
    except Exception as e:
        return {"error": f"Nie udało się wczytać stacji: {e}"}, 500

    results = []
    for uid, row in gdf.reset_index().iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue
        st_lon = float(geom.x)
        st_lat = float(geom.y)
        dist = haversine_km(lat, lon, st_lat, st_lon)
        results.append({
            "uid": int(uid),
            "name": row.get("name") or row.get("nazwa") or f"station_{uid}",
            "lon": st_lon,
            "lat": st_lat,
            "distance_km": round(dist, 3)
        })


    results.sort(key=lambda x: x["distance_km"])
    return jsonify(results[:n])



@app.route("/distance")
def distance():
    try:
        from_uid = request.args.get("from", type=int)
        to_uid = request.args.get("to", type=int)
        if from_uid is None or to_uid is None:
            return {"error": "provide from and to as uid query params"}, 400

        gdf = load_stations_gdf()


        if not (0 <= from_uid < len(gdf)) or not (0 <= to_uid < len(gdf)):
            return {"error": "uid out of range"}, 400

        p_from = gdf.iloc[from_uid]
        p_to = gdf.iloc[to_uid]
        geom_from = p_from.geometry
        geom_to = p_to.geometry
        if geom_from is None or geom_to is None:
            return {"error": "missing geometry"}, 400

        lat1, lon1 = float(geom_from.y), float(geom_from.x)
        lat2, lon2 = float(geom_to.y), float(geom_to.x)

        dist_km = haversine_km(lat1, lon1, lat2, lon2)


        line_geojson = {
            "type": "Feature",
            "properties": {
                "from_uid": int(from_uid),
                "to_uid": int(to_uid),
                "distance_km": dist_km
            },
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [lon1, lat1],
                    [lon2, lat2]
                ]
            }
        }

        result = {
            "from": {"uid": int(from_uid), "name": p_from.get("name") or None, "lon": lon1, "lat": lat1},
            "to": {"uid": int(to_uid), "name": p_to.get("name") or None, "lon": lon2, "lat": lat2},
            "distance_km": dist_km,
            "line": line_geojson
        }
        return jsonify(result)

    except Exception as e:
        return {"error": str(e)}, 500



@app.route("/stations.geojson")
def stations_geojson():
    try:
        gdf = gpd.read_file(STATIONS_PATH, layer="stations")
        return jsonify(gdf.to_json())
    except Exception as e:
        return {"error": str(e)}, 500


@app.route("/lines.geojson")
def lines_geojson():
    try:
        gdf = gpd.read_file(LINES_PATH, layer="railway")
        return jsonify(gdf.to_json())
    except Exception as e:
        return {"error": str(e)}, 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)