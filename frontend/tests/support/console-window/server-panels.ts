/** Compile a caller's named real panels with their existing real children. */
import { serverCompiler, type Rewrite } from '../server-render';
import { pathToFileURL } from 'node:url';
import { render } from 'svelte/server';
export async function serverPanels(directory: string, panels: readonly (readonly [file: string, name: string])[]) {
  const compiled = serverCompiler(directory);
const rewrite: Rewrite[] = [
	['$lib/components/ChartReadout.svelte', './ChartReadout.server.mjs'],
	['./ChartReadout.svelte', './ChartReadout.server.mjs'],
	['../components/ChartReadout.svelte', './ChartReadout.server.mjs'],
	['$lib/components/Panel.svelte', './Panel.server.mjs'],
	['$lib/components/TargetBar.svelte', './TargetBar.server.mjs'],
	['$lib/charts/Chart.svelte', './Chart.server.mjs'],
	['$lib/components/RateControl.svelte', './RateControl.server.mjs'],
	['$lib/components/ShapeSwitch.svelte', './ShapeSwitch.server.mjs'],
	['./RankedList.svelte', './RankedList.server.mjs'],
	['./Sparkline.svelte', './Sparkline.server.mjs'],
	['./run-axis', '$lib/console/machine/run-axis'],
	['./frame', '$lib/charts/frame'],
	['./readout', '$lib/charts/readout'],
	['./engine', '$lib/charts/engine']
];
const files = [
	['src/lib/components/ChartReadout.svelte', 'ChartReadout'],
	['src/lib/components/Panel.svelte', 'Panel'],
	['src/lib/components/TargetBar.svelte', 'TargetBar'],
	['src/lib/charts/Chart.svelte', 'Chart'],
	['src/lib/components/RateControl.svelte', 'RateControl'],
	['src/lib/components/ShapeSwitch.svelte', 'ShapeSwitch'],
	['src/lib/components/RankedList.svelte', 'RankedList'],
	['src/lib/components/Sparkline.svelte', 'Sparkline'],
] as const;
  const modules: [string, string][] = [];
  for (const [file,name] of files) modules.push([name, await compiled(file, name, rewrite)]);
  for (const [file, name] of panels) {
    if (files.some(([, child]) => child === name)) continue;
    modules.push([name, await compiled(file, name, rewrite)]);
  }
  const drawn: Record<string, (props: Record<string, unknown>) => string> = {};
  for (const [name,module] of modules) {
    const component = (await import(pathToFileURL(module).href)).default;
    drawn[name] = (props) => render(component, { props }).body;
  }
  return { drawn, stripStyles: compiled.css.get('ChartReadout') ?? '' };
}
