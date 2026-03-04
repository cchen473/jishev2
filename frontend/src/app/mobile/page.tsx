"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import MarkdownDisplay from "@/components/MarkdownDisplay";
import {
  getAuthToken,
  submitEarthquakeReport,
  submitEarthquakeReportWithMedia,
  type FieldReport,
} from "@/lib/api";
import { toBackendAbsoluteUrl } from "@/lib/runtime-config";

const BUILDING_OPTIONS = ["住宅楼", "老旧砖混房", "钢结构厂房", "学校/医院", "商场/写字楼", "其他"];

function parseCoordinate(value: string, min: number, max: number): number | null {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed < min || parsed > max) {
    return null;
  }
  return parsed;
}

export default function MobileLanding() {
  const [token, setToken] = useState("");
  const [lat, setLat] = useState("");
  const [lng, setLng] = useState("");
  const [feltLevel, setFeltLevel] = useState("5");
  const [buildingType, setBuildingType] = useState(BUILDING_OPTIONS[0]);
  const [structureNotes, setStructureNotes] = useState("");
  const [description, setDescription] = useState("");
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<{
    report: FieldReport;
    shelterAdvice: string[];
    analysisStatus: string;
  } | null>(null);

  useEffect(() => {
    setToken(getAuthToken());
  }, []);

  const handleLoadCurrentLocation = () => {
    if (!navigator.geolocation) {
      setError("当前浏览器不支持定位，请手动填写经纬度。");
      return;
    }
    setError("");
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setLat(position.coords.latitude.toFixed(6));
        setLng(position.coords.longitude.toFixed(6));
      },
      () => {
        setError("定位失败，请检查定位权限或手动填写经纬度。");
      },
      { enableHighAccuracy: true, timeout: 10000 },
    );
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!token) {
      setError("请先在主站登录后再提交。");
      return;
    }

    const latValue = parseCoordinate(lat.trim(), -90, 90);
    const lngValue = parseCoordinate(lng.trim(), -180, 180);
    const feltValue = Number(feltLevel);

    if (latValue === null || lngValue === null) {
      setError("请填写有效经纬度。");
      return;
    }
    if (!Number.isFinite(feltValue) || feltValue < 1 || feltValue > 12) {
      setError("震感等级需在 1 到 12 之间。");
      return;
    }
    if (!buildingType.trim()) {
      setError("请选择建筑类型。");
      return;
    }

    setLoading(true);
    setError("");
    try {
      let response: {
        status: string;
        report: FieldReport;
        shelter_advice: string[];
        analysis_status: string;
      };

      if (imageFile) {
        const formData = new FormData();
        formData.append("lat", String(latValue));
        formData.append("lng", String(lngValue));
        formData.append("felt_level", String(feltValue));
        formData.append("building_type", buildingType.trim());
        formData.append("structure_notes", structureNotes.trim());
        formData.append("description", description.trim());
        formData.append("image", imageFile);
        response = await submitEarthquakeReportWithMedia(formData, token);
      } else {
        response = await submitEarthquakeReport(
          {
            lat: latValue,
            lng: lngValue,
            felt_level: feltValue,
            building_type: buildingType.trim(),
            structure_notes: structureNotes.trim(),
            description: description.trim(),
          },
          token,
        );
      }

      setResult({
        report: response.report,
        shelterAdvice: response.shelter_advice ?? [],
        analysisStatus: response.analysis_status ?? "unknown",
      });
    } catch (submitError: unknown) {
      if (
        typeof submitError === "object" &&
        submitError !== null &&
        "response" in submitError &&
        typeof (submitError as { response?: unknown }).response === "object"
      ) {
        const detail = (
          submitError as { response?: { data?: { detail?: unknown } } }
        ).response?.data?.detail;
        if (typeof detail === "string" && detail.trim()) {
          setError(detail);
        } else {
          setError("提交失败，请稍后重试。");
        }
      } else {
        setError("提交失败，请稍后重试。");
      }
    } finally {
      setLoading(false);
    }
  };

  const adviceMarkdown =
    result && result.shelterAdvice.length > 0
      ? result.shelterAdvice.map((item, index) => `${index + 1}. ${item}`).join("\n")
      : "";

  return (
    <div className="min-h-screen bg-[var(--bg-canvas)] px-4 py-6 text-[var(--text-primary)] sm:px-6">
      <div className="mx-auto max-w-3xl space-y-4">
        <section className="ui-panel rounded-2xl border p-5 shadow-[var(--shadow-panel)]">
          <h1 className="font-title text-2xl tracking-[0.02em]">居民地震上报入口</h1>
          <p className="mt-2 text-sm text-[var(--text-secondary)]">
            可上传周边现场图片，系统会返回针对当前环境的避险建议。
          </p>
          <div className="mt-3 flex flex-wrap gap-2 text-xs">
            <span className="rounded-lg border border-[var(--line-soft)] px-2 py-1 text-[var(--text-secondary)]">
              API 认证：{token ? "已就绪" : "未登录"}
            </span>
            <button
              type="button"
              className="ui-btn ui-btn-ghost ui-focus px-2.5 py-1"
              onClick={() => setToken(getAuthToken())}
            >
              刷新登录态
            </button>
            <Link href="/" className="ui-btn ui-btn-ghost ui-focus px-2.5 py-1">
              去主站登录
            </Link>
          </div>
        </section>

        <section className="ui-panel rounded-2xl border p-5 shadow-[var(--shadow-panel)]">
          <form className="space-y-3" onSubmit={handleSubmit}>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1.5">
                <label className="text-xs text-[var(--text-secondary)]">纬度</label>
                <input
                  className="ui-input ui-focus"
                  placeholder="例如 31.230416"
                  value={lat}
                  onChange={(event) => setLat(event.target.value)}
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-xs text-[var(--text-secondary)]">经度</label>
                <input
                  className="ui-input ui-focus"
                  placeholder="例如 121.473701"
                  value={lng}
                  onChange={(event) => setLng(event.target.value)}
                />
              </div>
            </div>

            <button
              type="button"
              className="ui-btn ui-btn-ghost ui-focus px-3 py-2 text-xs"
              onClick={handleLoadCurrentLocation}
            >
              使用当前位置
            </button>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1.5">
                <label className="text-xs text-[var(--text-secondary)]">震感等级（1-12）</label>
                <input
                  className="ui-input ui-focus"
                  type="number"
                  min={1}
                  max={12}
                  value={feltLevel}
                  onChange={(event) => setFeltLevel(event.target.value)}
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-xs text-[var(--text-secondary)]">建筑类型</label>
                <select
                  className="ui-input ui-focus"
                  value={buildingType}
                  onChange={(event) => setBuildingType(event.target.value)}
                >
                  {BUILDING_OPTIONS.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs text-[var(--text-secondary)]">房屋结构补充（可选）</label>
              <input
                className="ui-input ui-focus"
                placeholder="例如：框架结构，楼龄 15 年"
                value={structureNotes}
                onChange={(event) => setStructureNotes(event.target.value)}
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs text-[var(--text-secondary)]">现场描述（可选）</label>
              <textarea
                className="ui-input ui-focus min-h-20 resize-none"
                placeholder="例如：楼道有碎裂，电梯停运，一层可通行"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs text-[var(--text-secondary)]">现场图片（可选，建议上传）</label>
              <input
                type="file"
                accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp"
                onChange={(event) => {
                  const file = event.target.files?.[0] ?? null;
                  setImageFile(file);
                }}
                className="block w-full text-xs text-[var(--text-secondary)] file:mr-2 file:rounded-md file:border file:border-[var(--line-soft)] file:bg-[rgba(255,255,255,0.03)] file:px-2 file:py-1.5 file:text-xs file:text-[var(--text-primary)]"
              />
              {imageFile ? (
                <p className="text-xs text-[var(--text-secondary)]">已选择：{imageFile.name}</p>
              ) : null}
            </div>

            {error ? (
              <div className="rounded-xl border border-[rgba(201,123,115,0.4)] bg-[rgba(201,123,115,0.1)] px-3 py-2 text-xs text-[var(--danger)]">
                {error}
              </div>
            ) : null}

            <button
              type="submit"
              disabled={loading}
              className="ui-btn ui-btn-primary ui-focus w-full px-4 py-2.5 text-sm"
            >
              {loading ? "提交中..." : "提交上报并获取避险建议"}
            </button>
          </form>
        </section>

        {result ? (
          <section className="ui-panel rounded-2xl border p-5 shadow-[var(--shadow-panel)]">
            <div className="mb-2 flex items-center justify-between gap-2">
              <h2 className="font-title text-lg">建议结果</h2>
              <span className="rounded-lg border border-[var(--line-soft)] px-2 py-1 font-mono text-[10px] text-[var(--text-secondary)]">
                {result.analysisStatus}
              </span>
            </div>
            <div className="space-y-1 text-xs text-[var(--text-secondary)]">
              <p>
                坐标：{result.report.lat.toFixed(5)}, {result.report.lng.toFixed(5)}
              </p>
              <p>震感：{result.report.felt_level} 级</p>
              <p>建筑：{result.report.building_type}</p>
              {result.report.image_url ? (
                <p>
                  现场图：
                  <a
                    className="ml-1 text-[var(--accent-strong)] underline underline-offset-2"
                    href={toBackendAbsoluteUrl(result.report.image_url)}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    查看原图
                  </a>
                </p>
              ) : null}
            </div>
            <div className="mt-3 rounded-xl border border-[var(--line-soft)] bg-[rgba(255,255,255,0.02)] p-3">
              {adviceMarkdown ? (
                <MarkdownDisplay content={adviceMarkdown} compact />
              ) : (
                <p className="text-xs text-[var(--text-secondary)]">暂无建议，请补充现场信息后重试。</p>
              )}
            </div>
          </section>
        ) : null}

        <section className="ui-panel rounded-2xl border p-4 text-xs text-[var(--text-secondary)] shadow-[var(--shadow-panel)]">
          如需原生体验，可使用 Flutter 客户端：`mobile/flutter_app`
        </section>
      </div>
    </div>
  );
}
