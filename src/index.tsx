import {
  ButtonItem,
  PanelSection,
  PanelSectionRow,
  staticClasses,
} from "@decky/ui";
import { callable, definePlugin, toaster } from "@decky/api";
import { useCallback, useEffect, useMemo, useState } from "react";
import { FaVolumeHigh } from "react-icons/fa";

type Mode = "auto" | "balanced" | "cinema" | "loud" | "bypass";

type DeviceInfo = {
  product_name?: string;
  product_version?: string;
  board_name?: string;
  audio_subsystem?: string;
  supported?: boolean;
  support_reason?: string;
};

type AudioDevice = {
  name: string;
  description: string;
  state?: string;
  active_port?: string;
  default?: boolean;
};

type AudioDevices = {
  outputs: AudioDevice[];
  inputs: AudioDevice[];
};

type PluginState = {
  mode?: Mode;
  setup_state?: "ready" | "dependency-missing" | "repair-needed" | "unsupported";
  setup_error?: string;
  runtime_ready?: boolean;
  easyeffects_installed?: boolean;
  easyeffects_service_active?: boolean;
  controller_service_active?: boolean;
  device?: DeviceInfo;

  effective_mode?: Mode | "unknown";
  effective_profile?: string;
  actual_profile?: string;
  default_sink?: string;
  default_source?: string;
  active_output_port?: string;
  routing_mode?: string;
  internal_active?: boolean;
  controller_ok?: boolean;
  easyeffects_ok?: boolean;
  request_id?: string;
  applied_request_id?: string;
  last_error?: string;
  dsp_status?: string;
  dsp_effects_present?: number;
  dsp_effects_expected?: number;
  audio_streams?: number;
  test_phase?: string;
  updated_at?: number;
};

const getState = callable<[], PluginState>("get_state");
const setMode = callable<[mode: Mode], PluginState>("set_mode");
const reapply = callable<[], PluginState>("reapply");
const abTest = callable<[], PluginState>("ab_test");
const repairSetup = callable<[], PluginState>("repair_setup");
const installEasyEffects = callable<[], PluginState>("install_easyeffects");
const resetFactoryPresets = callable<[], PluginState>("reset_factory_presets");
const listAudioDevices = callable<[], AudioDevices>("list_audio_devices");
const setOutputDevice = callable<[name: string], PluginState>("set_output_device");
const setInputDevice = callable<[name: string], PluginState>("set_input_device");

const isPolish = (navigator.language || "").toLowerCase().startsWith("pl");

const TEXT = {
  pl: {
    status: "Stan",
    ready: "Gotowe",
    applying: "Zastosowywanie profilu",
    dspActive: "DSP aktywny",
    presetReady: "Preset gotowy",
    bypass: "Bypass aktywny",
    warning: "Wymaga uwagi",
    error: "Błąd",
    setup: "Konfiguracja",
    selected: "Wybrany",
    effective: "Efektywny",
    easyEffects: "EasyEffects",
    dsp: "DSP",
    output: "Wyjście",
    audio: "Audio",
    audioDevices: "Urządzenia audio",
    outputs: "Wyjście",
    inputs: "Wejście",
    outputChanged: "Wyjście audio zmienione",
    inputChanged: "Wejście audio zmienione",
    builtIn: "Wbudowane głośniki",
    hdmi: "HDMI / dock",
    bluetooth: "Bluetooth",
    usb: "USB audio",
    external: "Inne wyjście",
    unknown: "Nieznane",
    active: "aktywny",
    inactive: "brak aktywnego strumienia",
    profiles: "Profil",
    auto: "Auto",
    balanced: "Balanced",
    cinema: "Cinema",
    loud: "Loud",
    bypassMode: "Bypass",
    autoSub: "Głośniki: Balanced · HDMI/BT/USB: Bypass",
    balancedSub: "Najbardziej uniwersalny profil głośników",
    cinemaSub: "Pełniejszy dół, dialogi i szersza scena",
    loudSub: "Większa głośność odczuwalna",
    bypassSub: "Bez dodatkowego DSP",
    actions: "Narzędzia",
    reapply: "Zastosuj ponownie",
    ab: "Test A/B · 2 s Bypass",
    advanced: "Diagnostyka zaawansowana",
    hideAdvanced: "Ukryj diagnostykę",
    repair: "Napraw konfigurację",
    resetPresets: "Przywróć fabryczne presety pluginu",
    installEe: "Zainstaluj EasyEffects i skonfiguruj",
    installing: "Instalowanie…",
    unsupportedTitle: "Nieobsługiwane urządzenie",
    unsupportedBody: "v0.1 obsługuje wyłącznie ASUS ROG Xbox Ally X (RC73XA).",
    dependencyTitle: "Brak EasyEffects",
    dependencyBody: "Plugin wymaga Flatpaka EasyEffects. Możesz zainstalować go jednym przyciskiem.",
    repairTitle: "Runtime wymaga naprawy",
    repairBody: "Usługi audio nie są w pełni aktywne. Użyj naprawy konfiguracji.",
    confirmed: "Potwierdzony",
    service: "Usługa",
    controller: "Kontroler",
    device: "Urządzenie",
    lastError: "Ostatni błąd",
    noError: "brak",
    changed: "Profil zmieniony",
    failed: "Nie udało się wykonać operacji",
    resetDone: "Presety fabryczne przywrócone",
    repairDone: "Konfiguracja naprawiona",
    installedDone: "EasyEffects zainstalowany i skonfigurowany",
  },
  en: {
    status: "Status",
    ready: "Ready",
    applying: "Applying profile",
    dspActive: "DSP active",
    presetReady: "Preset ready",
    bypass: "Bypass active",
    warning: "Needs attention",
    error: "Error",
    setup: "Setup",
    selected: "Selected",
    effective: "Effective",
    easyEffects: "EasyEffects",
    dsp: "DSP",
    output: "Output",
    audio: "Audio",
    audioDevices: "Audio devices",
    outputs: "Output",
    inputs: "Input",
    outputChanged: "Audio output changed",
    inputChanged: "Audio input changed",
    builtIn: "Built-in speakers",
    hdmi: "HDMI / dock",
    bluetooth: "Bluetooth",
    usb: "USB audio",
    external: "Other output",
    unknown: "Unknown",
    active: "active",
    inactive: "no active stream",
    profiles: "Profile",
    auto: "Auto",
    balanced: "Balanced",
    cinema: "Cinema",
    loud: "Loud",
    bypassMode: "Bypass",
    autoSub: "Speakers: Balanced · HDMI/BT/USB: Bypass",
    balancedSub: "General-purpose built-in speaker profile",
    cinemaSub: "Fuller bass, clearer dialogue and wider stage",
    loudSub: "Higher perceived loudness",
    bypassSub: "No additional DSP",
    actions: "Tools",
    reapply: "Reapply",
    ab: "A/B test · 2 s Bypass",
    advanced: "Advanced diagnostics",
    hideAdvanced: "Hide diagnostics",
    repair: "Repair setup",
    resetPresets: "Restore plugin factory presets",
    installEe: "Install EasyEffects and configure",
    installing: "Installing…",
    unsupportedTitle: "Unsupported device",
    unsupportedBody: "v0.1 supports ASUS ROG Xbox Ally X (RC73XA) only.",
    dependencyTitle: "EasyEffects is missing",
    dependencyBody: "The plugin requires the EasyEffects Flatpak. It can install it for you.",
    repairTitle: "Runtime needs repair",
    repairBody: "The audio services are not fully active. Use Repair setup.",
    confirmed: "Confirmed",
    service: "Service",
    controller: "Controller",
    device: "Device",
    lastError: "Last error",
    noError: "none",
    changed: "Profile changed",
    failed: "Operation failed",
    resetDone: "Factory presets restored",
    repairDone: "Setup repaired",
    installedDone: "EasyEffects installed and configured",
  },
};

const t = isPolish ? TEXT.pl : TEXT.en;

const MODES: Array<{ id: Mode; title: string; subtitle: string }> = [
  { id: "auto", title: t.auto, subtitle: t.autoSub },
  { id: "balanced", title: t.balanced, subtitle: t.balancedSub },
  { id: "cinema", title: t.cinema, subtitle: t.cinemaSub },
  { id: "loud", title: t.loud, subtitle: t.loudSub },
  { id: "bypass", title: t.bypassMode, subtitle: t.bypassSub },
];

function profileShort(profile?: string) {
  if (!profile) return "—";
  if (profile.endsWith("Experimental Balanced")) return "Balanced";
  if (profile.endsWith("Experimental Cinema")) return "Cinema";
  if (profile.endsWith("Experimental Loud")) return "Loud";
  if (profile.endsWith("Bypass")) return "Bypass";
  return profile;
}

function sinkShort(state?: PluginState | null) {
  if (!state) return "—";
  if (state.internal_active) return t.builtIn;
  const sink = (state.default_sink || "").toLowerCase();
  if (sink.includes("hdmi")) return t.hdmi;
  if (sink.includes("bluez") || sink.includes("bluetooth")) return t.bluetooth;
  if (sink.includes("usb")) return t.usb;
  if (!sink) return t.unknown;
  return t.external;
}

function dspText(state?: PluginState | null) {
  if (!state) return "—";
  const present = state.dsp_effects_present ?? 0;
  const expected = state.dsp_effects_expected ?? 5;
  switch (state.dsp_status) {
    case "chain-present":
      return `${t.dspActive} ${present}/${expected}`;
    case "waiting-audio":
      return t.presetReady;
    case "bypass-confirmed":
      return t.bypass;
    case "partial":
      return `${t.warning}: ${present}/${expected}`;
    case "chain-missing":
      return isPolish
        ? "UWAGA: audio aktywne, ale dźwięk omija DSP"
        : "WARNING: audio is active but bypasses the DSP chain";
    case "profile-mismatch":
      return isPolish ? "Profil EasyEffects nie zgadza się z żądanym" : "EasyEffects profile mismatch";
    case "bypass-mismatch":
      return isPolish ? "Bypass nie został potwierdzony" : "Bypass was not confirmed";
    case "ee-offline":
      return isPolish ? "EasyEffects niedostępny" : "EasyEffects unavailable";
    default:
      return t.unknown;
  }
}

function headline(state: PluginState | null, busy: boolean) {
  if (busy || state?.test_phase) return `⏳ ${t.applying}`;
  if (!state) return `⏳ ${t.setup}`;
  if (state.setup_state === "unsupported") return `⚠️ ${t.unsupportedTitle}`;
  if (state.setup_state === "dependency-missing") return `⚠️ ${t.dependencyTitle}`;
  if (state.setup_state === "repair-needed") return `⚠️ ${t.repairTitle}`;
  if (state.last_error) return `❌ ${t.error}`;
  if (state.dsp_status === "chain-missing" || state.dsp_status === "partial") return `⚠️ ${t.warning}`;
  if (state.dsp_status === "bypass-confirmed") return `✅ ${t.bypass}`;
  if (state.dsp_status === "chain-present") return `✅ ${t.dspActive} 5/5`;
  if (state.easyeffects_ok) return `✅ ${t.confirmed}`;
  return `⚠️ ${t.warning}`;
}

function Content() {
  const [state, setState] = useState<PluginState | null>(null);
  const [busy, setBusy] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [devices, setDevices] = useState<AudioDevices>({ outputs: [], inputs: [] });

  const refresh = useCallback(async () => {
    try {
      const [nextState, nextDevices] = await Promise.all([getState(), listAudioDevices()]);
      setState(nextState);
      setDevices(nextDevices);
    } catch (error) {
      console.error("ROG Ally Audio: refresh failed", error);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 1000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const runAction = useCallback(
    async (action: () => Promise<PluginState>, successText: string) => {
      if (busy) return;
      setBusy(true);
      try {
        const next = await action();
        setState(next);
        toaster.toast({ title: "ROG Ally Audio", body: successText });
      } catch (error) {
        console.error("ROG Ally Audio operation failed", error);
        toaster.toast({
          title: "ROG Ally Audio",
          body: `${t.failed}: ${String(error)}`,
        });
      } finally {
        setBusy(false);
        window.setTimeout(() => void refresh(), 400);
      }
    },
    [busy, refresh],
  );

  const ready = Boolean(state?.runtime_ready);
  const supported = state?.device?.supported !== false;
  const audioText = (state?.audio_streams ?? 0) > 0
    ? `${t.active} (${state?.audio_streams})`
    : t.inactive;

  const setupPanel = useMemo(() => {
    if (!state) return null;
    if (state.setup_state === "unsupported") {
      return (
        <PanelSection title={t.setup}>
          <PanelSectionRow>
            <div style={{ width: "100%", lineHeight: "1.45" }}>
              <b>⚠️ {t.unsupportedTitle}</b>
              <div style={{ marginTop: "6px", opacity: 0.8 }}>{t.unsupportedBody}</div>
              <div style={{ marginTop: "6px", fontSize: "12px", opacity: 0.65 }}>
                {state.device?.product_name || t.unknown} {state.device?.product_version || ""}
              </div>
            </div>
          </PanelSectionRow>
        </PanelSection>
      );
    }
    if (state.setup_state === "dependency-missing") {
      return (
        <PanelSection title={t.setup}>
          <PanelSectionRow>
            <div style={{ width: "100%", lineHeight: "1.45" }}>
              <b>{t.dependencyTitle}</b>
              <div style={{ marginTop: "5px", opacity: 0.8 }}>{t.dependencyBody}</div>
            </div>
          </PanelSectionRow>
          <PanelSectionRow>
            <ButtonItem
              layout="below"
              disabled={busy || !supported}
              onClick={() => void runAction(installEasyEffects, t.installedDone)}
            >
              {busy ? t.installing : t.installEe}
            </ButtonItem>
          </PanelSectionRow>
        </PanelSection>
      );
    }
    if (state.setup_state === "repair-needed") {
      return (
        <PanelSection title={t.setup}>
          <PanelSectionRow>
            <div style={{ width: "100%", lineHeight: "1.45" }}>
              <b>⚠️ {t.repairTitle}</b>
              <div style={{ marginTop: "5px", opacity: 0.8 }}>{t.repairBody}</div>
              {state.setup_error ? (
                <div style={{ marginTop: "6px", fontSize: "12px", opacity: 0.65 }}>{state.setup_error}</div>
              ) : null}
            </div>
          </PanelSectionRow>
          <PanelSectionRow>
            <ButtonItem
              layout="below"
              disabled={busy}
              onClick={() => void runAction(repairSetup, t.repairDone)}
            >
              {t.repair}
            </ButtonItem>
          </PanelSectionRow>
        </PanelSection>
      );
    }
    return null;
  }, [busy, runAction, state, supported]);

  return (
    <>
      <PanelSection title={t.status}>
        <PanelSectionRow>
          <div style={{ width: "100%", lineHeight: "1.48" }}>
            <div style={{ fontSize: "18px", fontWeight: 700, marginBottom: "7px" }}>
              {headline(state, busy)}
            </div>
            <div><b>{t.selected}:</b> {state?.mode ? MODES.find((m) => m.id === state.mode)?.title ?? state.mode : "—"}</div>
            <div><b>{t.effective}:</b> {profileShort(state?.effective_profile)}</div>
            <div><b>{t.easyEffects}:</b> {profileShort(state?.actual_profile)}</div>
            <div><b>{t.dsp}:</b> {dspText(state)}</div>
            <div><b>{t.output}:</b> {sinkShort(state)}</div>
            <div><b>{t.audio}:</b> {audioText}</div>
            {state?.last_error ? (
              <div style={{ marginTop: "7px", fontSize: "12px", opacity: 0.72, wordBreak: "break-word" }}>
                <b>{t.lastError}:</b> {state.last_error}
              </div>
            ) : null}
          </div>
        </PanelSectionRow>
      </PanelSection>

      {setupPanel}

      {ready ? (
        <PanelSection title={t.audioDevices}>
          <PanelSectionRow>
            <div style={{ width: "100%", fontWeight: 700 }}>{t.outputs}</div>
          </PanelSectionRow>
          {devices.outputs.map((device) => (
            <PanelSectionRow key={`out-${device.name}`}>
              <ButtonItem
                layout="below"
                disabled={busy}
                onClick={() => void runAction(() => setOutputDevice(device.name), t.outputChanged)}
              >
                {device.default ? "● " : ""}{device.description}
                {device.active_port ? (
                  <div style={{ fontSize: "11px", opacity: 0.62, marginTop: "2px" }}>{device.active_port}</div>
                ) : null}
              </ButtonItem>
            </PanelSectionRow>
          ))}
          <PanelSectionRow>
            <div style={{ width: "100%", fontWeight: 700, marginTop: "4px" }}>{t.inputs}</div>
          </PanelSectionRow>
          {devices.inputs.map((device) => (
            <PanelSectionRow key={`in-${device.name}`}>
              <ButtonItem
                layout="below"
                disabled={busy}
                onClick={() => void runAction(() => setInputDevice(device.name), t.inputChanged)}
              >
                {device.default ? "● " : ""}{device.description}
                {device.active_port ? (
                  <div style={{ fontSize: "11px", opacity: 0.62, marginTop: "2px" }}>{device.active_port}</div>
                ) : null}
              </ButtonItem>
            </PanelSectionRow>
          ))}
        </PanelSection>
      ) : null}

      <PanelSection title={t.profiles}>
        {MODES.map((mode) => (
          <PanelSectionRow key={mode.id}>
            <ButtonItem
              layout="below"
              disabled={busy || !ready}
              onClick={() => void runAction(() => setMode(mode.id), `${t.changed}: ${mode.title}`)}
            >
              {state?.mode === mode.id ? "● " : ""}{mode.title}
              <div style={{ fontSize: "12px", opacity: 0.7, marginTop: "3px" }}>{mode.subtitle}</div>
            </ButtonItem>
          </PanelSectionRow>
        ))}
      </PanelSection>

      <PanelSection title={t.actions}>
        <PanelSectionRow>
          <ButtonItem
            layout="below"
            disabled={busy || !ready}
            onClick={() => void runAction(reapply, t.confirmed)}
          >
            {t.reapply}
          </ButtonItem>
        </PanelSectionRow>
        <PanelSectionRow>
          <ButtonItem
            layout="below"
            disabled={busy || !ready || !state?.internal_active}
            onClick={() => void runAction(abTest, t.confirmed)}
          >
            {t.ab}
          </ButtonItem>
        </PanelSectionRow>
        <PanelSectionRow>
          <ButtonItem layout="below" onClick={() => setShowAdvanced((value) => !value)}>
            {showAdvanced ? t.hideAdvanced : t.advanced}
          </ButtonItem>
        </PanelSectionRow>
      </PanelSection>

      {showAdvanced ? (
        <PanelSection title={t.advanced}>
          <PanelSectionRow>
            <div style={{ width: "100%", fontSize: "12px", lineHeight: "1.5", opacity: 0.85 }}>
              <div><b>{t.service}:</b> {state?.easyeffects_service_active ? "OK" : "OFF"}</div>
              <div><b>{t.controller}:</b> {state?.controller_service_active ? "OK" : "OFF"}</div>
              <div><b>{t.device}:</b> {state?.device?.product_name || t.unknown}</div>
              <div><b>DSP nodes:</b> {state?.dsp_effects_present ?? 0}/{state?.dsp_effects_expected ?? 5}</div>
              <div><b>Sink:</b> {state?.default_sink || t.unknown}</div>
              <div><b>Source:</b> {state?.default_source || t.unknown}</div>
              <div><b>Port:</b> {state?.active_output_port || "—"}</div>
              <div><b>Routing:</b> {state?.routing_mode || "—"}</div>
              <div><b>request:</b> {state?.request_id || "—"}</div>
              <div><b>applied:</b> {state?.applied_request_id || "—"}</div>
              <div><b>{t.lastError}:</b> {state?.last_error || t.noError}</div>
            </div>
          </PanelSectionRow>
          <PanelSectionRow>
            <ButtonItem
              layout="below"
              disabled={busy || !supported || !state?.easyeffects_installed}
              onClick={() => void runAction(repairSetup, t.repairDone)}
            >
              {t.repair}
            </ButtonItem>
          </PanelSectionRow>
          <PanelSectionRow>
            <ButtonItem
              layout="below"
              disabled={busy || !ready}
              onClick={() => void runAction(resetFactoryPresets, t.resetDone)}
            >
              {t.resetPresets}
            </ButtonItem>
          </PanelSectionRow>
        </PanelSection>
      ) : null}
    </>
  );
}

export default definePlugin(() => ({
  name: "ROG Ally Audio",
  titleView: <div className={staticClasses.Title}>ROG Ally Audio</div>,
  content: <Content />,
  icon: <FaVolumeHigh />,
  onDismount() {
    console.log("ROG Ally Audio unloaded");
  },
}));
