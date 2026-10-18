import * as THREE from 'three';
import type { FoodTrace } from './interactables.ts';
import { rolloutProjects } from './rolloutProgress.ts';

type SiteModel = { root: THREE.Group; pad: THREE.Mesh; frame: THREE.Group; roof: THREE.Mesh; counter: THREE.Mesh };

/** Illustrative site furniture. Visibility follows committed milestones, not a browser job queue. */
export class RolloutSiteLayer {
  readonly group = new THREE.Group();
  private models = new Map<string, SiteModel>();
  private trace: FoodTrace | null = null;

  setTrace(trace: FoodTrace): void {
    this.clear(); this.trace = trace;
    if (trace.policy !== 'council' || !trace.rollout_events.length) return;
    for (const site of trace.sites.filter(item => item.type === 'council')) {
      const root = new THREE.Group(); root.position.set(site.point[0], 0, site.point[1]);
      const pad = new THREE.Mesh(new THREE.RingGeometry(12, 16, 48), new THREE.MeshBasicMaterial({
        color: '#c6a354', transparent: true, opacity: .85, side: THREE.DoubleSide, depthTest: false,
      }));
      pad.rotation.x = -Math.PI / 2; pad.position.y = .65; pad.renderOrder = 4; root.add(pad);
      const frame = new THREE.Group(); root.add(frame);
      for (const x of [-9, 9]) for (const z of [-7, 7]) {
        const post = new THREE.Mesh(new THREE.BoxGeometry(.9, 14, .9), new THREE.MeshStandardMaterial({ color: '#9c8459' }));
        post.position.set(x, 7, z); frame.add(post);
      }
      const roof = new THREE.Mesh(new THREE.ConeGeometry(17, 7, 4), new THREE.MeshStandardMaterial({ color: '#6b9376', roughness: .8 }));
      roof.rotation.y = Math.PI / 4; roof.position.y = 17; root.add(roof);
      const counter = new THREE.Mesh(new THREE.BoxGeometry(15, 4, 7), new THREE.MeshStandardMaterial({ color: '#ead9a8' }));
      counter.position.set(0, 2, 0); root.add(counter);
      this.group.add(root); this.models.set(site.id, { root, pad, frame, roof, counter });
    }
    this.update(0);
  }

  update(seconds: number): void {
    if (!this.trace) return;
    for (const project of rolloutProjects(this.trace, seconds)) {
      const model = this.models.get(project.site.id);
      if (!model) continue;
      const ready = project.completed.some(event => event.stage === 'readiness');
      const commissioned = project.completed.some(event => event.stage === 'commissioning');
      model.frame.visible = ready && project.status !== 'blocked';
      model.roof.visible = commissioned && project.status !== 'blocked';
      model.counter.visible = project.status === 'operating';
      (model.pad.material as THREE.MeshBasicMaterial).color.set(project.status === 'blocked' ? '#d76555'
        : project.status === 'closed' ? '#8c9895' : project.status === 'operating' ? '#75bd87' : '#dfb960');
      (model.roof.material as THREE.MeshStandardMaterial).color.set(project.status === 'closed' ? '#85948c' : '#6b9376');
    }
  }

  private clear(): void {
    this.group.traverse(object => {
      if (object instanceof THREE.Mesh) {
        object.geometry.dispose();
        for (const material of Array.isArray(object.material) ? object.material : [object.material]) material.dispose();
      }
    });
    this.group.clear(); this.models.clear();
  }
  dispose(): void { this.clear(); this.trace = null; }
}
