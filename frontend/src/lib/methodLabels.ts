/** Mapeia códigos da API para rótulos de badge do painel. */
export type MethodCode =
  | 'DIRETO'
  | 'REGRA_DIRETA'
  | 'FALLBACK_PARCIAL'
  | 'ML'
  | 'FALLBACK_CATEGORIA'
  | 'FALLBACK_N1'
  | 'SEM_EQUIPE'
  | string

export type MethodBadgeInfo = {
  code: string
  label: string
  hint: string
  className: string
}

const MAP: Record<string, Omit<MethodBadgeInfo, 'code'>> = {
  DIRETO: {
    label: 'Regra direta',
    hint: 'Palavra-chave única em arqaux.',
    className: 'bg-accent-soft text-ink ring-accent/40',
  },
  REGRA_DIRETA: {
    label: 'Regra direta',
    hint: 'Palavra-chave única em arqaux.',
    className: 'bg-accent-soft text-ink ring-accent/40',
  },
  FALLBACK_PARCIAL: {
    label: 'Regra parcial',
    hint: 'Várias palavras; uma equipe vence.',
    className: 'bg-warn-soft text-ink ring-warn/40',
  },
  ML: {
    label: 'Modelo ML',
    hint: 'Classificação do modelo treinado.',
    className: 'bg-ok-soft text-ink ring-ok/40',
  },
  FALLBACK_CATEGORIA: {
    label: 'Pela categoria',
    hint: 'Equipe pelo tipo do chamado no GLPI.',
    className: 'bg-warn-soft text-ink ring-warn/40',
  },
  FALLBACK_N1: {
    label: 'Padrão N1',
    hint: 'Nenhuma regra, ML ou categoria casou; equipe N1.',
    className: 'bg-danger-soft text-ink ring-danger/40',
  },
  SEM_EQUIPE: {
    label: 'Sem equipe',
    hint: 'Não foi possível definir equipe.',
    className: 'bg-canvas text-muted ring-line',
  },
}

export function resolveMethodBadge(raw: unknown): MethodBadgeInfo | null {
  if (raw === null || raw === undefined || String(raw).trim() === '') return null
  const code = String(raw).trim().toUpperCase()
  const info = MAP[code]
  if (info) return { code, ...info }
  return {
    code,
    label: code,
    hint: code,
    className: 'bg-canvas text-muted ring-line',
  }
}
