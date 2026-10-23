import {useEffect, useRef} from 'react';
import type {CompanionConfig} from './companionApi';

export function useRetainedTask(config: CompanionConfig | undefined, jobs: readonly {id:string}[] | undefined,
  selected: string | null, select: (id: string) => void) {
  const loaded = useRef<string | null>(null);
  useEffect(() => {
    if (!config || !jobs) return;
    const name = config.runtime_id ? `nyaru-task-${config.runtime_id}` : null;
    const key = name ?? 'legacy';
    if (loaded.current !== key) {
      loaded.current = key;
      const saved = name ? document.cookie.split(';').map(item => item.trim()).find(item => item.startsWith(name + '='))?.slice(name.length + 1) : null;
      if (!selected && jobs.length) select(jobs.find(job => job.id === saved)?.id ?? jobs[0].id);
      return;
    }
    if (!selected && jobs.length) select(jobs[0].id);
    if (name && selected && jobs.some(job => job.id === selected)) {
      document.cookie = `${name}=${selected}; Path=/; Max-Age=31536000; SameSite=Strict`;
    }
  }, [config, jobs, selected, select]);
}
