import type { Data } from "./lib/data";
import type { Facts } from "./lib/facts";

export type Lang = "pt" | "en";

export interface Ctx {
  d: Data;
  f: Facts;
  num: (n: number, digits?: number) => string;
  pct: (x: number) => string;
  lang: Lang;
  busTime: string;
}

export function makeCtx(lang: Lang, d: Data, f: Facts): Ctx {
  const locale = lang === "pt" ? "pt-BR" : "en-US";
  // Bus snapshot time shown in Belo Horizonte local time, formatted per locale.
  const busTime = d.bus
    ? new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short", timeZone: "America/Sao_Paulo" }).format(new Date(d.bus.ts_utc))
    : "";
  return {
    d,
    f,
    lang,
    busTime,
    num: (n, digits = 0) =>
      new Intl.NumberFormat(locale, { maximumFractionDigits: digits, minimumFractionDigits: digits }).format(n),
    pct: (x) => new Intl.NumberFormat(locale, { style: "percent", maximumFractionDigits: 0 }).format(x),
  };
}

export const WEEKDAYS: Record<Lang, string[]> = {
  pt: ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"],
  en: ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
};
export const WEEKDAYS_SHORT: Record<Lang, string[]> = {
  pt: ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"],
  en: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
};

export const ROAD_USERS: Record<Lang, Record<string, string>> = {
  pt: { motorcycle: "Motociclistas", pedestrian: "Pedestres", car: "Automóveis", bicycle: "Ciclistas", truck: "Caminhões", bus: "Ônibus", other: "Outros" },
  en: { motorcycle: "Motorcyclists", pedestrian: "Pedestrians", car: "Car occupants", bicycle: "Cyclists", truck: "Truck occupants", bus: "Bus occupants", other: "Other" },
};

/** "CENTRO-SUL" -> "Centro-Sul", "VENDA NOVA" -> "Venda Nova" */
export const regionalName = (s: string) =>
  s.toLowerCase().replace(/(^|[\s-])(\p{L})/gu, (_, sep: string, c: string) => sep + c.toUpperCase());

type S = (c: Ctx) => string;
type Dict = Record<string, S>;

const pt: Dict = {
  skip: () => "Pular para o conteúdo",
  "nav.label": () => "Seções",
  "nav.decade": () => "Década",
  "nav.clock": () => "Relógio",
  "nav.map": () => "Mapa",
  "nav.who": () => "Quem",
  "nav.buses": () => "Ônibus",
  "nav.ml": () => "IA",
  "nav.method": () => "Método",
  "lang.other": () => "EN",
  "lang.sr": () => "Switch to English",

  "hero.eyebrow": (c) => `Belo Horizonte · dados abertos ${c.d.summary.first_year}–${c.d.summary.last_year}`,
  "hero.title1": (c) => `${c.num(Math.round(c.d.summary.crashes_per_day_last_year))} sinistros com vítima.`,
  "hero.title2": () => "Todos os dias.",
  "hero.statLabel": (c) => `sinistros com vítima registrados em ${c.d.summary.last_year}`,
  "hero.lead": () =>
    "Um estudo independente sobre onde, quando e com quem o trânsito de BH fere — e o que aprendizado de máquina pode fazer a respeito.",
  "hero.cta": () => "Começar",

  "decade.eyebrow": () => "A década",
  "decade.title": (c) => `Caiu até ${c.f.minYear.year}. Voltou a subir.`,
  "decade.lead": (c) =>
    `Em ${c.f.lastYear.year} foram ${c.num(c.f.lastYear.deaths)} mortes no trânsito — ` +
    (c.f.deathsHighestSince ? `o maior número desde ${c.f.deathsHighestSince}.` : "o maior número da série."),
  "decade.caption": (c) =>
    `Sinistros com vítima (acima) e mortes (abaixo, em âmbar) por ano, ${c.d.summary.first_year}–${c.d.summary.last_year}. Fonte: BHTrans/PBH.`,
  "decade.crashes": () => "sinistros",
  "decade.deaths": () => "mortes",

  "clock.eyebrow": () => "O relógio",
  "clock.title": () => "O trânsito fere na hora de ir e de voltar.",
  "clock.step1": (c) =>
    `Cada célula é uma hora da semana, somando ${c.f.years}. Quanto mais escura, mais sinistros com vítima.`,
  "clock.step2": (c) => `De segunda a sexta, dois picos se repetem: ${c.f.amPeak}h e ${c.f.pmPeak}h.`,
  "clock.step3": (c) =>
    `O pior momento da semana: ${WEEKDAYS.pt[c.f.worst.weekday]}, ${c.f.worst.hour}h — ${c.num(c.f.worst.n)} sinistros em cinco anos.`,
  "clock.caption": (c) => `Sinistros com vítima por dia da semana e hora, ${c.f.years} (n = ${c.num(c.d.clock.n)}).`,
  "clock.tableCaption": () => "Sinistros por dia da semana (linhas) e hora (colunas)",

  "map.eyebrow": () => "O mapa",
  "map.title": () => "Onde acontece.",
  "map.aria": (c) => `Mapa de Belo Horizonte com sinistros com vítima por hexágono, ${c.f.years}.`,
  "map.intro": (c) =>
    `Cada hexágono cobre cerca de 0,7 km². A cor soma os sinistros com vítima de ${c.f.years}.`,
  "map.outro": () => "Nove regionais. Nenhuma fica de fora.",
  "map.legendLow": () => "menos",
  "map.legendHigh": () => "mais sinistros",

  "who.eyebrow": () => "Quem",
  "who.title": (c) => `${c.pct(c.f.motoShare)} dos sinistros com vítima envolvem uma moto.`,
  "who.lead": (c) =>
    `Das ${c.num(c.d.summary.deaths_recent)} mortes em ${c.f.years}, motociclistas e pedestres somam ${c.pct(c.f.motoPedShare)}.`,
  "who.caption": (c) => `Mortes por tipo de usuário da via, ${c.f.years}. Fonte: BHTrans/PBH.`,

  "buses.eyebrow": () => "Agora",
  "buses.title": (c) => (c.d.bus ? `${c.num(c.d.bus.vehicles)} ônibus. Um retrato.` : "Ônibus em tempo real."),
  "buses.lead": (c) =>
    c.d.bus
      ? `Posições GPS publicadas pela PBH em ${c.busTime}. Entre os que estavam em movimento, a velocidade mediana era ${c.num(c.d.bus.median_speed_moving_kmh)} km/h.`
      : "O retrato do GPS não pôde ser carregado nesta versão.",
  "buses.caption": (c) =>
    c.d.bus
      ? `${c.pct(c.d.bus.share_reporting_under_5kmh)} reportavam menos de 5 km/h — inclui pontos, terminais e garagens, então não é medida de congestionamento. O coletor do projeto foi feito para guardar essas posições a cada 15–60 minutos.`
      : "",
  "buses.aria": (c) => (c.d.bus ? `Pontos de GPS de ${c.num(c.d.bus.vehicles)} ônibus em Belo Horizonte.` : "Mapa de ônibus indisponível."),
  "buses.stamp": (c) => (c.d.bus ? `Retrato · ${c.busTime} · ${c.num(c.d.bus.lines)} linhas` : ""),

  "ml.eyebrow": () => "Próximos passos",
  "ml.title": () => "O que aprendizado de máquina pode fazer.",
  "ml.lead": () => "Quatro frentes, cada uma validada com dados reais ou simulação antes de virar proposta. Nenhum resultado de modelo aparece aqui até existir.",

  "method.eyebrow": () => "Método",
  "method.title": () => "Fontes e limites.",
  "method.sourcesTitle": () => "Fontes",
  "method.limitsTitle": () => "Limites",
  footer: (c) =>
    `Projeto de portfólio, independente da PBH. Dados de sinistros até ${c.d.summary.last_year}. Código: github.com/Dias0202/Transito_bh (privado).`,
};

const en: Dict = {
  skip: () => "Skip to content",
  "nav.label": () => "Sections",
  "nav.decade": () => "Decade",
  "nav.clock": () => "Clock",
  "nav.map": () => "Map",
  "nav.who": () => "Who",
  "nav.buses": () => "Buses",
  "nav.ml": () => "AI",
  "nav.method": () => "Method",
  "lang.other": () => "PT",
  "lang.sr": () => "Mudar para português",

  "hero.eyebrow": (c) => `Belo Horizonte, Brazil · open data ${c.d.summary.first_year}–${c.d.summary.last_year}`,
  "hero.title1": (c) => `${c.num(Math.round(c.d.summary.crashes_per_day_last_year))} injury crashes.`,
  "hero.title2": () => "Every single day.",
  "hero.statLabel": (c) => `crashes with victims recorded in ${c.d.summary.last_year}`,
  "hero.lead": () =>
    "An independent study of where, when and whom Belo Horizonte's traffic hurts — and what machine learning can do about it.",
  "hero.cta": () => "Begin",

  "decade.eyebrow": () => "The decade",
  "decade.title": (c) => `Down until ${c.f.minYear.year}. Up again since.`,
  "decade.lead": (c) =>
    `${c.f.lastYear.year} saw ${c.num(c.f.lastYear.deaths)} traffic deaths — ` +
    (c.f.deathsHighestSince ? `the highest since ${c.f.deathsHighestSince}.` : "the highest on record."),
  "decade.caption": (c) =>
    `Crashes with victims (top) and deaths (bottom, amber) per year, ${c.d.summary.first_year}–${c.d.summary.last_year}. Source: BHTrans/PBH.`,
  "decade.crashes": () => "crashes",
  "decade.deaths": () => "deaths",

  "clock.eyebrow": () => "The clock",
  "clock.title": () => "Traffic hurts on the way to work and back.",
  "clock.step1": (c) =>
    `Each cell is one hour of the week, summed over ${c.f.years}. Darker means more injury crashes.`,
  "clock.step2": (c) => `Monday to Friday, two peaks repeat: ${c.f.amPeak}:00 and ${c.f.pmPeak}:00.`,
  "clock.step3": (c) =>
    `The worst hour of the week: ${WEEKDAYS.en[c.f.worst.weekday]} at ${c.f.worst.hour}:00 — ${c.num(c.f.worst.n)} crashes in five years.`,
  "clock.caption": (c) => `Injury crashes by weekday and hour, ${c.f.years} (n = ${c.num(c.d.clock.n)}).`,
  "clock.tableCaption": () => "Crashes by weekday (rows) and hour (columns)",

  "map.eyebrow": () => "The map",
  "map.title": () => "Where it happens.",
  "map.aria": (c) => `Map of Belo Horizonte with injury crashes per hexagon, ${c.f.years}.`,
  "map.intro": (c) => `Each hexagon covers about 0.7 km². Colour sums injury crashes over ${c.f.years}.`,
  "map.outro": () => "Nine districts. None is spared.",
  "map.legendLow": () => "fewer",
  "map.legendHigh": () => "more crashes",

  "who.eyebrow": () => "Who",
  "who.title": (c) => `${c.pct(c.f.motoShare)} of injury crashes involve a motorcycle.`,
  "who.lead": (c) =>
    `Of the ${c.num(c.d.summary.deaths_recent)} deaths in ${c.f.years}, motorcyclists and pedestrians account for ${c.pct(c.f.motoPedShare)}.`,
  "who.caption": (c) => `Deaths by road user, ${c.f.years}. Source: BHTrans/PBH.`,

  "buses.eyebrow": () => "Right now",
  "buses.title": (c) => (c.d.bus ? `${c.num(c.d.bus.vehicles)} buses. One snapshot.` : "Buses in real time."),
  "buses.lead": (c) =>
    c.d.bus
      ? `GPS positions published by the city on ${c.busTime} (Brasília time). Among buses in motion, the median speed was ${c.num(c.d.bus.median_speed_moving_kmh)} km/h.`
      : "The GPS snapshot could not be loaded in this build.",
  "buses.caption": (c) =>
    c.d.bus
      ? `${c.pct(c.d.bus.share_reporting_under_5kmh)} reported under 5 km/h — that includes stops, terminals and depots, so it is not a congestion measure. The project's collector is built to store these positions every 15–60 minutes.`
      : "",
  "buses.aria": (c) => (c.d.bus ? `GPS points of ${c.num(c.d.bus.vehicles)} buses in Belo Horizonte.` : "Bus map unavailable."),
  "buses.stamp": (c) => (c.d.bus ? `Snapshot · ${c.busTime} (Brasília) · ${c.num(c.d.bus.lines)} lines` : ""),

  "ml.eyebrow": () => "Next steps",
  "ml.title": () => "What machine learning can do.",
  "ml.lead": () => "Four fronts, each validated on real data or in simulation before it becomes a proposal. No model result is shown here until one exists.",

  "method.eyebrow": () => "Method",
  "method.title": () => "Sources and limits.",
  "method.sourcesTitle": () => "Sources",
  "method.limitsTitle": () => "Limits",
  footer: (c) =>
    `Portfolio project, independent from the city of Belo Horizonte. Crash data through ${c.d.summary.last_year}. Code: github.com/Dias0202/Transito_bh (private).`,
};

export const DICT: Record<Lang, Dict> = { pt, en };

export function regionalStep(c: Ctx, r: Data["regionals"][number]): string {
  const name = regionalName(r.regional);
  return c.lang === "pt"
    ? `${name}: ${c.num(r.crashes)} sinistros com vítima, ${c.num(r.fatal_crashes)} com morte. No hexágono mais crítico, ${c.num(r.top_cell_crashes)}.`
    : `${name}: ${c.num(r.crashes)} injury crashes, ${c.num(r.fatal_crashes)} fatal. In its worst hexagon alone, ${c.num(r.top_cell_crashes)}.`;
}

export interface Front { title: string; body: string; status: string; state: "collecting" | "next" | "planned" | "result" }

export const FRONTS: Record<Lang, Front[]> = {
  pt: [
    { title: "Previsão de congestionamento", body: "Redes neurais em grafo espaço-temporais preveem a velocidade por trecho de 15 a 60 minutos à frente, treinadas com tempos de viagem TomTom, radares e GPS dos ônibus.", status: "Coletor pronto", state: "collecting" },
    { title: "Risco de sinistro", body: "Teste em 2024: 5% dos hexágono-horários concentram 23% dos sinistros. O gradient boosting empatou com um ranking simples (taxa do local × perfil horário). Próximo: incluir volume dos radares e geometria viária.", status: "Primeiro resultado", state: "result" },
    { title: "Semáforos adaptativos", body: "Aprendizado por reforço controla semáforos em simulações SUMO de áreas piloto e é comparado a planos de tempo fixo.", status: "Planejado", state: "planned" },
    { title: "Prioridade para ônibus", body: "Cenários de faixa exclusiva e prioridade semafórica, medidos com o GPS real da frota antes e depois.", status: "Planejado", state: "planned" },
  ],
  en: [
    { title: "Congestion forecasting", body: "Spatio-temporal graph neural networks predict per-segment speed 15 to 60 minutes ahead, trained on TomTom travel times, radar counts and bus GPS.", status: "Collector ready", state: "collecting" },
    { title: "Crash risk", body: "Tested on 2024: 5% of hexagon-hours hold 23% of crashes. Gradient boosting tied a simple ranking (place rate × hourly profile). Next: add radar volumes and road geometry.", status: "First result", state: "result" },
    { title: "Adaptive traffic signals", body: "Reinforcement learning controls signals in SUMO simulations of pilot areas and is compared with fixed-time plans.", status: "Planned", state: "planned" },
    { title: "Bus priority", body: "Dedicated-lane and signal-priority scenarios, measured with the fleet's real GPS before and after.", status: "Planned", state: "planned" },
  ],
};

export function methodLists(c: Ctx): { sources: string[]; limits: string[] } {
  const s = c.d.summary;
  if (c.lang === "pt") {
    return {
      sources: [
        `Sinistros com vítima ${s.first_year}–${s.last_year}: BHTrans/PBH, portal dados.pbh.gov.br (ocorrências, veículos e pessoas envolvidas).`,
        "Posição dos ônibus: PBH, “Tempo Real Ônibus — Coordenada atualizada”.",
        "Hexágonos: sistema H3, resolução 8.",
        "Mapa base: © OpenStreetMap contributors, © CARTO.",
      ],
      limits: [
        "Só entram sinistros com vítima; colisões sem feridos não fazem parte da base.",
        `Coordenadas de 2011–2015 usam outro formato e foram convertidas para o UTM dos anos seguintes. ${c.num(s.geocode_placeholders_removed)} registros caíam num mesmo ponto vindo de cinco ou mais regionais — um geocódigo padrão — e foram retirados do mapa.`,
        `${c.pct(s.share_without_coords)} dos sinistros não têm coordenada válida e ficam fora do mapa, mas contam nos totais.`,
        "Retrato dos ônibus é um instante, não uma média.",
      ],
    };
  }
  return {
    sources: [
      `Injury crashes ${s.first_year}–${s.last_year}: BHTrans/city of Belo Horizonte, dados.pbh.gov.br (crashes, vehicles and people involved).`,
      "Bus positions: city of Belo Horizonte, “Tempo Real Ônibus — Coordenada atualizada”.",
      "Hexagons: H3 grid, resolution 8.",
      "Basemap: © OpenStreetMap contributors, © CARTO.",
    ],
    limits: [
      "Only crashes with victims are included; property-damage-only collisions are not in the data.",
      `2011–2015 coordinates use another layout and were converted to the later years' UTM grid. ${c.num(s.geocode_placeholders_removed)} records sat on one spot reported from five or more districts — a default geocode — and were removed from the map.`,
      `${c.pct(s.share_without_coords)} of crashes have no valid coordinate; they are off the map but in the totals.`,
      "The bus picture is a single instant, not an average.",
    ],
  };
}
