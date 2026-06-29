// Illustrative DEMO numbers for the stats screen — NOT real data. Replace with your own.
// (Pull your real public metrics from your own channels when you build a promo.)

export const GRAND_TOTAL_VIEWS = 1_250_000_000;
export const GRAND_TOTAL_VIEWS_FMT = '1.25B';
export const TOTAL_CLIPS = 12_000;

// Sample top clips (made-up titles + view counts for the demo screen).
export const TOP_CLIPS: { text: string; views: number; viewsFmt: string; platform: string }[] = [
  { text: 'The one habit that changed everything', views: 12_400_000, viewsFmt: '12.4M', platform: 'Instagram' },
  { text: 'Why most plans fail',                    views: 8_900_000,  viewsFmt: '8.9M',  platform: 'YouTube' },
  { text: 'Start before you feel ready',            views: 7_600_000,  viewsFmt: '7.6M',  platform: 'YouTube' },
  { text: 'The math nobody shows you',              views: 6_800_000,  viewsFmt: '6.8M',  platform: 'TikTok' },
  { text: 'How to make your first $1,000',          views: 6_100_000,  viewsFmt: '6.1M',  platform: 'Instagram' },
  { text: 'The mistake that cost me a year',        views: 5_400_000,  viewsFmt: '5.4M',  platform: 'Instagram' },
  { text: 'Do the reps',                            views: 4_900_000,  viewsFmt: '4.9M',  platform: 'YouTube' },
];

// Per-platform footprint (sample totals, standard platform colors).
export const PLATFORMS: { name: string; viewsFmt: string; color: string }[] = [
  { name: 'Instagram', viewsFmt: '520M', color: '#e1306c' },
  { name: 'YouTube',   viewsFmt: '410M', color: '#ff0033' },
  { name: 'X',         viewsFmt: '180M', color: '#1d9bf0' },
  { name: 'TikTok',    viewsFmt: '110M', color: '#25f4ee' },
  { name: 'Facebook',  viewsFmt: '30M',  color: '#1877f2' },
];
