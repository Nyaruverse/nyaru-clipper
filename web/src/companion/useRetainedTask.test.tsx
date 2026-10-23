import {act, renderHook} from '@testing-library/react';
import {useState} from 'react';
import {expect, it} from 'vitest';
import {useRetainedTask} from './useRetainedTask';
import type {CompanionConfig} from './companionApi';

it('restores a known selection after config arrives and retains it across remounts', () => {
  const jobs = [{id: 'first'}, {id: 'second'}];
  const config: CompanionConfig = {runtime_id:'fixture-retention', ready:true, missing:[], translation_configured:false};
  document.cookie = 'nyaru-task-fixture-retention=second; Path=/';
  const hook = renderHook(({ready}: {ready:boolean}) => {
    const [selected, select] = useState<string | null>(null);
    useRetainedTask(ready ? config : undefined, jobs, selected, select);
    return {selected, select};
  }, {initialProps:{ready:false}});
  expect(hook.result.current.selected).toBeNull();
  hook.rerender({ready:true});
  expect(hook.result.current.selected).toBe('second');
  act(() => hook.result.current.select('first'));
  expect(document.cookie).toContain('nyaru-task-fixture-retention=first');
  hook.unmount();
  const reopened = renderHook(() => {
    const [selected, select] = useState<string | null>(null);
    useRetainedTask(config, jobs, selected, select);
    return selected;
  });
  expect(reopened.result.current).toBe('first');
  reopened.unmount();
  document.cookie = 'nyaru-task-fixture-retention=; Path=/; Max-Age=0';
});
