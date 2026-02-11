export type ScheduleType = 'free_text' | 'per_hour' | 'per_day' | 'specific_times';

export interface MedicationScheduleFields {
  schedule_type: ScheduleType;
  every_hours: number | null;
  times_per_day: number | null;
  take_morning: boolean;
  take_noon: boolean;
  take_evening: boolean;
  take_bedtime: boolean;
  take_with_breakfast: boolean;
  take_with_lunch: boolean;
  take_with_dinner: boolean;
}

export const defaultMedicationSchedule = (): MedicationScheduleFields => ({
  schedule_type: 'free_text',
  every_hours: null,
  times_per_day: null,
  take_morning: false,
  take_noon: false,
  take_evening: false,
  take_bedtime: false,
  take_with_breakfast: false,
  take_with_lunch: false,
  take_with_dinner: false,
});

export const inferScheduleFromFrequency = (frequencyInput: string): MedicationScheduleFields => {
  const frequency = String(frequencyInput || '').toLowerCase().trim();
  const parsed = defaultMedicationSchedule();
  if (!frequency) {
    return parsed;
  }

  const hourMatch =
    frequency.match(/\b(?:every|q)\s*(\d{1,2})\s*(?:h|hr|hour|hours)\b/) ||
    frequency.match(/\bevery\s*(\d{1,2})\s*(?:hours|hour)\b/);
  if (hourMatch) {
    parsed.schedule_type = 'per_hour';
    parsed.every_hours = Number(hourMatch[1]);
    return parsed;
  }

  const perDayMatch = frequency.match(/\b(\d{1,2})\s*(?:x|times?)\s*(?:per\s*)?day\b/);
  if (perDayMatch) {
    parsed.schedule_type = 'per_day';
    parsed.times_per_day = Number(perDayMatch[1]);
  } else if (
    frequency.includes('four times daily') ||
    frequency.includes('four times a day') ||
    /\bqid\b/.test(frequency)
  ) {
    parsed.schedule_type = 'per_day';
    parsed.times_per_day = 4;
  } else if (
    frequency.includes('three times daily') ||
    frequency.includes('three times a day') ||
    /\btid\b/.test(frequency)
  ) {
    parsed.schedule_type = 'per_day';
    parsed.times_per_day = 3;
  } else if (
    frequency.includes('twice daily') ||
    frequency.includes('twice a day') ||
    /\bbid\b/.test(frequency)
  ) {
    parsed.schedule_type = 'per_day';
    parsed.times_per_day = 2;
  } else if (
    frequency.includes('once daily') ||
    frequency.includes('once a day') ||
    /\bdaily\b/.test(frequency) ||
    /\bod\b/.test(frequency)
  ) {
    parsed.schedule_type = 'per_day';
    parsed.times_per_day = 1;
  }

  parsed.take_morning = /\bmorning\b/.test(frequency) || /\bam\b/.test(frequency);
  parsed.take_noon = /\bnoon\b/.test(frequency) || /\bafternoon\b/.test(frequency);
  parsed.take_evening = /\bevening\b/.test(frequency) || /\bnight\b/.test(frequency);
  parsed.take_bedtime = /\bbedtime\b/.test(frequency) || /\bhs\b/.test(frequency) || frequency.includes('before sleep');
  parsed.take_with_breakfast = /\bbreakfast\b/.test(frequency);
  parsed.take_with_lunch = /\blunch\b/.test(frequency);
  parsed.take_with_dinner = /\bdinner\b/.test(frequency) || /\bsupper\b/.test(frequency);

  if (
    parsed.take_morning ||
    parsed.take_noon ||
    parsed.take_evening ||
    parsed.take_bedtime ||
    parsed.take_with_breakfast ||
    parsed.take_with_lunch ||
    parsed.take_with_dinner
  ) {
    parsed.schedule_type = 'specific_times';
  }

  return parsed;
};

export const buildFrequencyFromSchedule = (
  schedule: MedicationScheduleFields,
  fallbackFrequency: string
): string => {
  if (schedule.schedule_type === 'per_hour' && schedule.every_hours) {
    return `Every ${schedule.every_hours} hours`;
  }

  if (schedule.schedule_type === 'per_day' && schedule.times_per_day) {
    if (schedule.times_per_day === 1) {
      return 'Once per day';
    }
    return `${schedule.times_per_day} times per day`;
  }

  if (schedule.schedule_type === 'specific_times') {
    const labels: string[] = [];
    if (schedule.take_morning) labels.push('morning');
    if (schedule.take_noon) labels.push('noon');
    if (schedule.take_evening) labels.push('evening');
    if (schedule.take_bedtime) labels.push('bedtime');
    if (schedule.take_with_breakfast) labels.push('with breakfast');
    if (schedule.take_with_lunch) labels.push('with lunch');
    if (schedule.take_with_dinner) labels.push('with dinner');
    if (labels.length > 0) {
      return `At ${labels.join(', ')}`;
    }
  }

  return String(fallbackFrequency || '').trim();
};

export const isScheduleComplete = (
  schedule: MedicationScheduleFields,
  frequency: string
): boolean => {
  if (schedule.schedule_type === 'per_hour') {
    return !!schedule.every_hours && schedule.every_hours > 0;
  }
  if (schedule.schedule_type === 'per_day') {
    return !!schedule.times_per_day && schedule.times_per_day > 0;
  }
  if (schedule.schedule_type === 'specific_times') {
    return (
      schedule.take_morning ||
      schedule.take_noon ||
      schedule.take_evening ||
      schedule.take_bedtime ||
      schedule.take_with_breakfast ||
      schedule.take_with_lunch ||
      schedule.take_with_dinner
    );
  }
  return String(frequency || '').trim().length > 0;
};
