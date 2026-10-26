import {useEffect, useState} from 'react';
import {parseTime, time} from './companionApi';
import type {TopicRange} from './useTopicDraft';

interface Props {
  readonly range: TopicRange;
  readonly duration: number;
  readonly disabled: boolean;
  readonly onChange: (range: TopicRange) => void;
}
export function TopicRangeEditor({range, duration, disabled, onChange}: Props) {
  const [start, setStart] = useState(time(range.start_seconds));
  const [end, setEnd] = useState(time(range.end_seconds));
  const [error, setError] = useState('');
  useEffect(() => {setStart(time(range.start_seconds));setEnd(time(range.end_seconds));setError('');}, [range.start_seconds, range.end_seconds]);
  return <form className="topic-range-editor" onSubmit={event => {
    event.preventDefault();
    try {
      const start_seconds = parseTime(start), end_seconds = parseTime(end);
      if (end_seconds <= start_seconds || end_seconds > duration) {setError('出点须晚于入点，且不能超过视频时长。');return;}
      onChange({start_seconds, end_seconds});setError('');
    } catch (reason) {setError(reason instanceof Error ? reason.message : '请检查片段时间。');}
  }}>
    <fieldset disabled={disabled}><legend>当前高光范围</legend><div className="topic-range-fields">
      <label className="ny-field">入点<input className="ny-input" aria-label="高光入点" value={start} onChange={event => setStart(event.target.value)}/></label>
      <label className="ny-field">出点<input className="ny-input" aria-label="高光出点" value={end} onChange={event => setEnd(event.target.value)}/></label>
      <button className="ny-button" type="submit">应用片段范围</button>
    </div></fieldset>
    {error && <p role="alert" className="companion-error">{error}</p>}
  </form>;
}
