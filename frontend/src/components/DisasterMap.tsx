import Map, { Marker, NavigationControl } from "react-map-gl/mapbox";
import "mapbox-gl/dist/mapbox-gl.css";
import { getMapboxToken } from "@/lib/runtime-config";

interface DisasterMapProps {
  markers?: { lat: number; lng: number; type: string }[];
  centerLat?: number;
  centerLng?: number;
  initialZoom?: number;
  minZoom?: number;
}

function markerTone(type: string): { pulse: string; dot: string } {
  if (type === "fire") {
    return { pulse: "bg-red-400/70", dot: "bg-red-500" };
  }
  if (type === "flood") {
    return { pulse: "bg-sky-400/70", dot: "bg-sky-500" };
  }
  return { pulse: "bg-amber-300/70", dot: "bg-amber-500" };
}

export default function DisasterMap({
  markers = [],
  centerLat = 30.5728,
  centerLng = 104.0668,
  initialZoom = 16.8,
  minZoom = 14.8,
}: DisasterMapProps) {
  const mapboxToken = getMapboxToken();

  if (!mapboxToken) {
    return (
      <div className="h-full w-full rounded-2xl bg-zinc-900 border border-zinc-800 flex items-center justify-center p-6 text-zinc-400 text-sm">
        缺少地图令牌，请设置环境变量 <code className="mx-1">NEXT_PUBLIC_MAPBOX_TOKEN</code>
      </div>
    );
  }

  return (
    <Map
      key={`${centerLat.toFixed(4)}-${centerLng.toFixed(4)}-${initialZoom.toFixed(1)}`}
      initialViewState={{
        latitude: centerLat,
        longitude: centerLng,
        zoom: initialZoom,
        bearing: 0,
        pitch: 18,
      }}
      style={{ width: "100%", height: "100%", borderRadius: "1rem" }}
      minZoom={minZoom}
      mapStyle="mapbox://styles/mapbox/streets-v12"
      mapboxAccessToken={mapboxToken}
    >
      <NavigationControl position="top-right" />

      {/* Dynamic Markers */}
      {markers.map((marker, idx) => {
        const tone = markerTone(marker.type);
        return (
          <Marker
            key={idx}
            latitude={marker.lat}
            longitude={marker.lng}
            anchor="bottom"
          >
            <div className="relative flex items-center justify-center">
              <div className={`absolute inline-flex h-4 w-4 animate-ping rounded-full ${tone.pulse}`} />
              <div className={`relative inline-flex h-3.5 w-3.5 rounded-full border border-white/80 ${tone.dot}`} />
            </div>
          </Marker>
        );
      })}

    </Map>
  );
}
