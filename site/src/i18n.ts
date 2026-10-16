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

/** Rate ratio of one event from effects.json, as a signed whole percent (e.g. 14, -31). */
const fxPct = (c: Ctx, id: string) => {
  const e = c.d.effects?.events.find((x) => x.event === id);
  return e ? Math.round((e.irr - 1) * 100) : 0;
};
/** End of the hourly model period, e.g. "jul/2026" / "Jul 2026". */
const period = (c: Ctx) => {
  const t = c.d.effects?.through;
  if (!t) return String(c.d.summary.last_year);
  const d = new Date(`${t}T12:00:00`);
  return new Intl.DateTimeFormat(c.lang === "pt" ? "pt-BR" : "en-US", { month: "short", year: "numeric" }).format(d).replace(". de ", "/").replace(" de ", "/");
};
/** One decimal with a typographic sign: +1,0 / −0,3. */
const signed = (c: Ctx, x: number) => `${x < 0 ? "−" : "+"}${c.num(Math.abs(x), 1)}`;
const both = (c: Ctx) => {
  const ev = c.d.effects?.events;
  const a = ev?.find((x) => x.event === "rain_any")?.irr ?? 1;
  const b = ev?.find((x) => x.event === "first_rain")?.irr ?? 1;
  return Math.round((a * b - 1) * 100);
};

export const EVENT_LABELS: Record<Lang, Record<string, string>> = {
  pt: { rain_any: "Chuva na hora", first_rain: "Primeira chuva após 72 h secos", holiday: "Feriado", carnaval: "Carnaval", optional_day: "Ponto facultativo", day_after_holiday: "Dia após feriado", match: "Jogo da Série A em BH" },
  en: { rain_any: "Rain in the hour", first_rain: "First rain after 72 h dry", holiday: "Public holiday", carnaval: "Carnaval", optional_day: "Optional day off", day_after_holiday: "Day after a holiday", match: "Série A match in BH" },
};

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
  "decade.lead": (c) => {
    const { lastYear: l, prevYear: p } = c.f;
    const lead = `Em ${l.year}, ${c.num(l.crashes)} sinistros com vítima e ${c.num(l.deaths)} sinistros com morte`;
    if (c.f.deathsHighestSince === null) return `${lead} — o maior número da série.`;
    if (c.f.deathsHighestSince < p.year) return `${lead} — o maior número desde ${c.f.deathsHighestSince}.`;
    return `${lead}. Em ${p.year} tinham sido ${c.num(p.deaths)}${c.f.prevHighestSince ? `, o maior número desde ${c.f.prevHighestSince}` : ""}.`;
  },
  "decade.caption": (c) =>
    `Sinistros com vítima (acima) e sinistros com morte (abaixo, em âmbar) por ano, ${c.d.summary.first_year}–${c.d.summary.last_year}. Fonte: BHTrans/PBH.`,
  "decade.crashes": () => "sinistros",
  "decade.deaths": () => "sinistros com morte",

  "clock.eyebrow": () => "O relógio",
  "clock.title": () => "O trânsito fere na hora de ir e de voltar.",
  "clock.step1": (c) =>
    `Cada célula é uma hora da semana, somando ${c.f.years}. Quanto mais escura, mais sinistros com vítima.`,
  "clock.step2": (c) => `De segunda a sexta, dois picos se repetem: ${c.f.amPeak}h e ${c.f.pmPeak}h.`,
  "clock.step3": (c) =>
    `O pior momento da semana: ${WEEKDAYS.pt[c.f.worst.weekday]}, ${c.f.worst.hour}h — ${c.num(c.f.worst.n)} sinistros em cinco anos.`,
  "clock.caption": (c) => `Sinistros com vítima por dia da semana e hora, ${c.f.years} (n = ${c.num(c.d.clock.n)}).`,
  "clock.tableCaption": () => "Sinistros por dia da semana (linhas) e hora (colunas)",

  "nav.congestion": () => "Onde para",
  "cong.eyebrow": () => "Onde o trânsito para",
  "cong.title": (c) => {
    const s = c.d.congestion?.sites ?? [];
    const w = s.map((x) => x.worst).sort((p, q) => p - q);
    const med = w.length ? w[Math.floor(w.length / 2)] : 1;
    return `Nos pontos mais travados, o pico deixa os carros a ${c.pct(med)} da velocidade da madrugada.`;
  },
  "cong.lead": (c) =>
    c.d.congestion
      ? `Cada faixa é um dia útil médio num radar da BHTrans: a cor mostra a velocidade dos carros em relação à da madrugada. Os ${c.d.congestion.sites.length} pontos mais travados, de ${c.num(c.d.congestion.sites_total)} medidos.`
      : "",
  "cong.legendFree": () => "fluxo livre",
  "cong.legendSlow": () => "a 30% ou menos",
  "cong.caption": (c) =>
    c.d.congestion
      ? `Índice de velocidade = velocidade média dos carros na hora ÷ mediana da madrugada (0h–5h), por radar e sentido, dias úteis; ${c.num(c.d.congestion.days ?? 0)} dias de radar entre ${c.d.congestion.first_day ?? ""} e ${c.d.congestion.last_day ?? ""}. Valor à direita: pior hora. Fonte: BHTrans, contagens volumétricas de radares.`
      : "",

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
    `Das ${c.num(c.d.summary.deaths_recent)} mortes em ${c.f.peopleYears}, motociclistas e pedestres somam ${c.pct(c.f.motoPedShare)}.` +
    (c.d.exposure
      ? ` Nos radares da BHTrans, motos são ${c.pct(c.d.exposure.moto_share_of_passages)} das passagens, mas estão em ${c.pct(c.d.exposure.moto_share_of_crashes)} dos sinistros a até ${c.d.exposure.radius_m} m: por passagem, ${c.num(Math.round(c.d.exposure.rate_ratio))} vezes mais (IC ${c.num(Math.round(c.d.exposure.ci_low))}–${c.num(Math.round(c.d.exposure.ci_high))}).`
      : ""),
  "who.caption": (c) => `Mortes por tipo de usuário da via, ${c.f.peopleYears} (a base com pessoas envolvidas vai até ${c.d.summary.people_window?.[1] ?? c.d.summary.last_year}). Fonte: BHTrans/PBH.`,

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

  "nav.rain": () => "Chuva",
  "nav.risk": () => "Risco",
  "rain.eyebrow": () => "Quando o risco muda",
  "rain.title": () => "A primeira chuva é a mais perigosa.",
  "rain.step1": (c) =>
    `Uma hora com chuva tem ${fxPct(c, "rain_any")}% mais sinistros. Se é a primeira chuva depois de três dias secos, mais ${fxPct(c, "first_rain")}% — cerca de ${both(c)}% no total. A pista acumula óleo e poeira.`,
  "rain.step2": (c) =>
    `Feriado tira ${Math.abs(fxPct(c, "holiday"))}% dos sinistros; Carnaval, ${Math.abs(fxPct(c, "carnaval"))}%. É menos carro na rua — não uma rua mais segura.`,
  "rain.step3": (c) =>
    `E dia de jogo? Nas ${c.num(c.d.effects?.matches ?? 0)} partidas da Série A em BH, o efeito não se distingue de zero — nem na cidade, nem perto dos estádios.`,
  "rain.less": () => "menos sinistros",
  "rain.one": () => "hora comum",
  "rain.more": () => "mais sinistros",
  "rain.caption": (c) =>
    `Razão de taxas contra horas comparáveis (mesmo dia da semana, hora, mês e ano; pandemia controlada), com IC 95%. ${c.num(c.d.effects?.hours ?? 0)} horas, ${c.d.summary.first_year}–${period(c)}. Jogos: 2012–2024. Fontes: BHTrans, INMET (Pampulha), Brasileirão Série A.`,

  "risk.eyebrow": () => "Onde concentrar",
  "risk.title": (c) =>
    c.d.risk ? `${c.pct(0.05)} dos lugares-horário concentram ${c.pct(c.d.risk.top5)} dos sinistros.` : "",
  "risk.lead": (c) =>
    c.d.risk
      ? `Cada hexágono × hora da semana foi ordenado pelo risco previsto para ${c.d.risk.test_year}, sem olhar ${c.d.risk.test_year}. Priorizar o topo da lista captura ${c.num(c.d.risk.top5 / 0.05, 1)} vezes o que o acaso capturaria.`
      : "",
  "risk.note": (c) =>
    c.d.risk
      ? `Resultado honesto: o gradient boosting empatou com um ranking simples — taxa do local × perfil horário da cidade (diferença no topo de 5%: ${signed(c, c.d.risk.tie_ci_top5[0] * 100)} a ${signed(c, c.d.risk.tie_ci_top5[1] * 100)} p.p., IC 95%). Para priorizar fiscalização e engenharia, o simples basta.`
      : "",
  "risk.caption": (c) =>
    c.d.risk
      ? `Fração dos ${c.num(c.d.risk.crashes)} sinistros georreferenciados de ${c.d.risk.test_year} que cai nos k% de hexágono-horários de maior risco previsto (${c.num(c.d.risk.cells)} hexágonos × 168 horas).`
      : "",

  "nav.whatif": () => "E se",
  "whatif.eyebrow": () => "E se…",
  "whatif.title": () => "Simule o que muda com o que já foi medido.",
  "whatif.lead": (c) =>
    c.d.whatif
      ? `Cada cenário usa um efeito estimado com dados de BH e a sinistralidade dos últimos 24 meses. O número grande é o valor central; a faixa mostra 90% das ${c.num(5000)} simulações.`
      : "",
  "whatif.bumps.title": () => "Redutores de velocidade",
  "whatif.bumps.control": () => "Redutores novos:",
  "whatif.cameras.title": () => "Radares de volta",
  "whatif.cameras.control": () => "Estimativa do efeito do radar",
  "whatif.cameras.all": () => "Todo o período",
  "whatif.cameras.since": () => "Desde 2024",
  "whatif.rain.title": () => "Primeira chuva",
  "whatif.rain.control": () => "Fração do excesso evitada:",
  "whatif.chip.measured": () => "Efeito medido",
  "whatif.chip.assumption": () => "Fração: premissa",
  "whatif.chip.speedMeasured": () => "Velocidade medida",
  "whatif.chip.literature": () => "Efeito: literatura",
  "whatif.chip.lever": () => "Redução: premissa",
  "whatif.speed.title": () => "Velocidade nas avenidas",
  "whatif.speed.control": () => "Redução da velocidade média:",
  "whatif.unit": () => "sinistros com vítima a menos por ano",
  "whatif.foot": (c) =>
    c.d.whatif
      ? `Redutores: efeito medido −${Math.round((1 - c.d.whatif.bumps.effect) * 100)}% (IC ${Math.round((1 - c.d.whatif.bumps.effect_ci[1]) * 100)}–${Math.round((1 - c.d.whatif.bumps.effect_ci[0]) * 100)}%), aplicado só a ruas locais com sinistralidade dentro da faixa onde foi medido. Linha de base: ${c.d.whatif.window.replace("..", " a ")}. Simulação, não promessa: o resultado real depende de onde e como cada intervenção é feita.`
      : "",

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
  "decade.lead": (c) => {
    const { lastYear: l, prevYear: p } = c.f;
    const lead = `${l.year} saw ${c.num(l.crashes)} injury crashes and ${c.num(l.deaths)} fatal crashes`;
    if (c.f.deathsHighestSince === null) return `${lead} — the highest on record.`;
    if (c.f.deathsHighestSince < p.year) return `${lead} — the highest since ${c.f.deathsHighestSince}.`;
    return `${lead}. ${p.year} had ${c.num(p.deaths)}${c.f.prevHighestSince ? `, the highest since ${c.f.prevHighestSince}` : ""}.`;
  },
  "decade.caption": (c) =>
    `Crashes with victims (top) and fatal crashes (bottom, amber) per year, ${c.d.summary.first_year}–${c.d.summary.last_year}. Source: BHTrans/PBH.`,
  "decade.crashes": () => "crashes",
  "decade.deaths": () => "fatal crashes",

  "clock.eyebrow": () => "The clock",
  "clock.title": () => "Traffic hurts on the way to work and back.",
  "clock.step1": (c) =>
    `Each cell is one hour of the week, summed over ${c.f.years}. Darker means more injury crashes.`,
  "clock.step2": (c) => `Monday to Friday, two peaks repeat: ${c.f.amPeak}:00 and ${c.f.pmPeak}:00.`,
  "clock.step3": (c) =>
    `The worst hour of the week: ${WEEKDAYS.en[c.f.worst.weekday]} at ${c.f.worst.hour}:00 — ${c.num(c.f.worst.n)} crashes in five years.`,
  "clock.caption": (c) => `Injury crashes by weekday and hour, ${c.f.years} (n = ${c.num(c.d.clock.n)}).`,
  "clock.tableCaption": () => "Crashes by weekday (rows) and hour (columns)",

  "nav.congestion": () => "Gridlock",
  "cong.eyebrow": () => "Where traffic stops",
  "cong.title": (c) => {
    const s = c.d.congestion?.sites ?? [];
    const w = s.map((x) => x.worst).sort((p, q) => p - q);
    const med = w.length ? w[Math.floor(w.length / 2)] : 1;
    return `At the most congested sites, the peak leaves cars at ${c.pct(med)} of their night speed.`;
  },
  "cong.lead": (c) =>
    c.d.congestion
      ? `Each strip is an average weekday at a BHTrans radar: colour shows car speed relative to the night. The ${c.d.congestion.sites.length} most congested sites out of ${c.num(c.d.congestion.sites_total)} measured.`
      : "",
  "cong.legendFree": () => "free flow",
  "cong.legendSlow": () => "at 30% or less",
  "cong.caption": (c) =>
    c.d.congestion
      ? `Speed index = mean car speed in the hour ÷ night median (00:00–05:00), per radar and direction, weekdays; ${c.num(c.d.congestion.days ?? 0)} radar days between ${c.d.congestion.first_day ?? ""} and ${c.d.congestion.last_day ?? ""}. Right: worst hour. Source: BHTrans radar volumetric counts.`
      : "",

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
    `Of the ${c.num(c.d.summary.deaths_recent)} deaths in ${c.f.peopleYears}, motorcyclists and pedestrians account for ${c.pct(c.f.motoPedShare)}.` +
    (c.d.exposure
      ? ` At BHTrans radars, motorcycles are ${c.pct(c.d.exposure.moto_share_of_passages)} of passages but are in ${c.pct(c.d.exposure.moto_share_of_crashes)} of crashes within ${c.d.exposure.radius_m} m: per passage, ${c.num(Math.round(c.d.exposure.rate_ratio))} times more (CI ${c.num(Math.round(c.d.exposure.ci_low))}–${c.num(Math.round(c.d.exposure.ci_high))}).`
      : ""),
  "who.caption": (c) => `Deaths by road user, ${c.f.peopleYears} (the dataset with people involved ends in ${c.d.summary.people_window?.[1] ?? c.d.summary.last_year}). Source: BHTrans/PBH.`,

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

  "nav.rain": () => "Rain",
  "nav.risk": () => "Risk",
  "rain.eyebrow": () => "When risk changes",
  "rain.title": () => "The first rain is the most dangerous.",
  "rain.step1": (c) =>
    `An hour with rain has ${fxPct(c, "rain_any")}% more crashes. If it is the first rain after three dry days, another ${fxPct(c, "first_rain")}% — about ${both(c)}% in total. Oil and dust build up on the road.`,
  "rain.step2": (c) =>
    `Holidays remove ${Math.abs(fxPct(c, "holiday"))}% of crashes; Carnaval, ${Math.abs(fxPct(c, "carnaval"))}%. That is fewer cars on the road — not safer streets.`,
  "rain.step3": (c) =>
    `And match days? Across ${c.num(c.d.effects?.matches ?? 0)} Série A matches in BH, the effect is indistinguishable from zero — citywide and near the stadiums.`,
  "rain.less": () => "fewer crashes",
  "rain.one": () => "typical hour",
  "rain.more": () => "more crashes",
  "rain.caption": (c) =>
    `Rate ratio against comparable hours (same weekday, hour, month and year; pandemic controlled), with 95% CI. ${c.num(c.d.effects?.hours ?? 0)} hours, ${c.d.summary.first_year}–${period(c)}. Matches: 2012–2024. Sources: BHTrans, INMET (Pampulha), Brasileirão Série A.`,

  "risk.eyebrow": () => "Where to focus",
  "risk.title": (c) =>
    c.d.risk ? `${c.pct(0.05)} of place-hours hold ${c.pct(c.d.risk.top5)} of crashes.` : "",
  "risk.lead": (c) =>
    c.d.risk
      ? `Every hexagon × hour of the week was ranked by risk predicted for ${c.d.risk.test_year}, without looking at ${c.d.risk.test_year}. Prioritising the top of the list captures ${c.num(c.d.risk.top5 / 0.05, 1)} times what chance would.`
      : "",
  "risk.note": (c) =>
    c.d.risk
      ? `Honest result: gradient boosting tied a simple ranking — place rate × citywide hourly profile (top-5% difference: ${signed(c, c.d.risk.tie_ci_top5[0] * 100)} to ${signed(c, c.d.risk.tie_ci_top5[1] * 100)} pp, 95% CI). To prioritise enforcement and engineering, simple is enough.`
      : "",
  "risk.caption": (c) =>
    c.d.risk
      ? `Share of ${c.d.risk.test_year}'s ${c.num(c.d.risk.crashes)} geolocated crashes falling in the top-k% hexagon-hours by predicted risk (${c.num(c.d.risk.cells)} hexagons × 168 hours).`
      : "",

  "nav.whatif": () => "What if",
  "whatif.eyebrow": () => "What if…",
  "whatif.title": () => "Simulate what changes, using what was measured.",
  "whatif.lead": (c) =>
    c.d.whatif
      ? `Each scenario uses an effect estimated from BH data and the crash record of the last 24 months. The big number is the central value; the band shows 90% of ${c.num(5000)} simulations.`
      : "",
  "whatif.bumps.title": () => "Speed bumps",
  "whatif.bumps.control": () => "New speed bumps:",
  "whatif.cameras.title": () => "Cameras back",
  "whatif.cameras.control": () => "Camera effect estimate",
  "whatif.cameras.all": () => "Whole period",
  "whatif.cameras.since": () => "Since 2024",
  "whatif.rain.title": () => "First rain",
  "whatif.rain.control": () => "Share of the excess avoided:",
  "whatif.chip.measured": () => "Measured effect",
  "whatif.chip.assumption": () => "Share: assumption",
  "whatif.chip.speedMeasured": () => "Measured speeds",
  "whatif.chip.literature": () => "Effect: literature",
  "whatif.chip.lever": () => "Reduction: assumption",
  "whatif.speed.title": () => "Speed on the avenues",
  "whatif.speed.control": () => "Cut in mean speed:",
  "whatif.unit": () => "fewer injury crashes a year",
  "whatif.foot": (c) =>
    c.d.whatif
      ? `Speed bumps: measured effect −${Math.round((1 - c.d.whatif.bumps.effect) * 100)}% (CI ${Math.round((1 - c.d.whatif.bumps.effect_ci[1]) * 100)}–${Math.round((1 - c.d.whatif.bumps.effect_ci[0]) * 100)}%), applied only to local streets with crash rates inside the range where it was measured. Baseline: ${c.d.whatif.window.replace("..", " to ")}. A simulation, not a promise: real results depend on where and how each intervention is built.`
      : "",

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
    { title: "Risco de sinistro", body: "Teste em 2025: 5% dos hexágono-horários concentram 23% dos sinistros; para escolher onde agir, o gradient boosting empata com um ranking simples (taxa do local × perfil horário). No tempo, chuva soma 14% e a primeira chuva após 3 dias secos, mais 19%; feriados tiram 31%; jogos da Série A não mostraram efeito. Redutores de velocidade: cerca de 21% menos sinistros por perto.", status: "Primeiro resultado", state: "result" },
    { title: "Semáforos adaptativos", body: "Aprendizado por reforço controla semáforos em simulações SUMO de áreas piloto e é comparado a planos de tempo fixo.", status: "Planejado", state: "planned" },
    { title: "Prioridade para ônibus", body: "Cenários de faixa exclusiva e prioridade semafórica, medidos com o GPS real da frota antes e depois.", status: "Planejado", state: "planned" },
  ],
  en: [
    { title: "Congestion forecasting", body: "Spatio-temporal graph neural networks predict per-segment speed 15 to 60 minutes ahead, trained on TomTom travel times, radar counts and bus GPS.", status: "Collector ready", state: "collecting" },
    { title: "Crash risk", body: "Tested on 2025: 5% of hexagon-hours hold 23% of crashes; to choose where to act, gradient boosting ties a simple ranking (place rate × hourly profile). Over time, rain adds 14% and the first rain after 3 dry days another 19%; holidays remove 31%; Série A matches showed no effect. Speed bumps: about 21% fewer crashes nearby.", status: "First result", state: "result" },
    { title: "Adaptive traffic signals", body: "Reinforcement learning controls signals in SUMO simulations of pilot areas and is compared with fixed-time plans.", status: "Planned", state: "planned" },
    { title: "Bus priority", body: "Dedicated-lane and signal-priority scenarios, measured with the fleet's real GPS before and after.", status: "Planned", state: "planned" },
  ],
};

export function methodLists(c: Ctx): { sources: string[]; limits: string[] } {
  const s = c.d.summary;
  if (c.lang === "pt") {
    return {
      sources: [
        `Sinistros com vítima ${s.first_year}–${s.last_year}: BHTrans/PBH, portal dados.pbh.gov.br — base anual (ocorrências, veículos e pessoas, até ${s.people_window?.[1] ?? s.last_year}) e base mensal de ocorrências georreferenciadas (2016 em diante, completa até ${s.complete_through ?? s.last_year}).`,
        "Posição dos ônibus: PBH, “Tempo Real Ônibus — Coordenada atualizada”.",
        "Hexágonos: sistema H3, resolução 8.",
        "Chuva: INMET, estação automática A521 (Pampulha), dados horários.",
        "Feriados: nacionais, de Minas Gerais e municipais de BH. Jogos: Brasileirão Série A (base aberta de Adão Duque).",
        "Mapa base: © OpenStreetMap contributors, © CARTO.",
      ],
      limits: [
        "Só entram sinistros com vítima; colisões sem feridos não fazem parte da base.",
        "A série anual usa sinistros com morte (ao menos uma vítima fatal), não o número de mortos: a base mensal não traz as pessoas envolvidas.",
        `Coordenadas de 2011–2015 usam outro formato e foram convertidas para o UTM dos anos seguintes. ${c.num(s.geocode_placeholders_removed)} registros caíam num mesmo ponto vindo de cinco ou mais regionais — um geocódigo padrão — e foram retirados do mapa.`,
        `${c.pct(s.share_without_coords)} dos sinistros não têm coordenada válida e ficam fora do mapa, mas contam nos totais.`,
        "Retrato dos ônibus é um instante, não uma média.",
        "Jogos: só a Série A — Mineiro, Copa do Brasil, Libertadores e Série B ficam de fora. Chuva: uma estação para a cidade toda.",
      ],
    };
  }
  return {
    sources: [
      `Injury crashes ${s.first_year}–${s.last_year}: BHTrans/city of Belo Horizonte, dados.pbh.gov.br — yearly dataset (crashes, vehicles and people, to ${s.people_window?.[1] ?? s.last_year}) and monthly geolocated crash dataset (2016 on, complete to ${s.complete_through ?? s.last_year}).`,
      "Bus positions: city of Belo Horizonte, “Tempo Real Ônibus — Coordenada atualizada”.",
      "Hexagons: H3 grid, resolution 8.",
      "Rain: INMET automatic station A521 (Pampulha), hourly.",
      "Holidays: national, Minas Gerais and BH municipal. Matches: Brasileirão Série A (open dataset by Adão Duque).",
      "Basemap: © OpenStreetMap contributors, © CARTO.",
    ],
    limits: [
      "Only crashes with victims are included; property-damage-only collisions are not in the data.",
      "The yearly series counts fatal crashes (at least one death), not deaths: the monthly dataset has no people involved.",
      `2011–2015 coordinates use another layout and were converted to the later years' UTM grid. ${c.num(s.geocode_placeholders_removed)} records sat on one spot reported from five or more districts — a default geocode — and were removed from the map.`,
      `${c.pct(s.share_without_coords)} of crashes have no valid coordinate; they are off the map but in the totals.`,
      "The bus picture is a single instant, not an average.",
      "Matches: Série A only — state league, Copa do Brasil, Libertadores and Série B are missing. Rain: one station for the whole city.",
    ],
  };
}
