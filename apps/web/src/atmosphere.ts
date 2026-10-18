import * as THREE from 'three';

export type SkyColors = { top: THREE.Color; horizon: THREE.Color; sun: THREE.Color; sunDirection: THREE.Vector3 };

const vertexShader = /* glsl */ `
varying vec3 vDir;
void main() {
  vDir = mat3(modelMatrix) * position;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}`;

// Below the horizon the colour must equal `horizon` exactly: scene fog uses it so the ground blends into the sky.
const fragmentShader = /* glsl */ `
uniform vec3 top;
uniform vec3 horizon;
uniform vec3 sunColor;
uniform vec3 sunDirection;
varying vec3 vDir;
void main() {
  vec3 d = normalize(vDir);
  float h = d.y;
  vec3 c = mix(horizon, top, pow(smoothstep(0.0, 0.55, h), 0.75));
  float s = max(dot(d, sunDirection), 0.0);
  // Keep the broad glow faint: fog has no glow, so a strong one leaves a band where the city meets the sky.
  c += sunColor * (pow(s, 8.0) * 0.03 + pow(s, 64.0) * 0.15 + pow(s, 2000.0) * 2.0) * smoothstep(0.0, 0.08, h);
  gl_FragColor = vec4(h < 0.0 ? horizon : c, 1.0);
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`;

export class Sky {
  readonly mesh: THREE.Mesh;
  private readonly material: THREE.ShaderMaterial;
  private readonly envScene = new THREE.Scene();
  private readonly envMesh: THREE.Mesh;
  private readonly pmrem: THREE.PMREMGenerator;
  private envTarget: THREE.WebGLRenderTarget | null = null;

  constructor(renderer: THREE.WebGLRenderer) {
    this.material = new THREE.ShaderMaterial({
      uniforms: {
        top: { value: new THREE.Color(0x6f9fd8) },
        horizon: { value: new THREE.Color(0xd6e4ee) },
        sunColor: { value: new THREE.Color(0xfff2d6) },
        sunDirection: { value: new THREE.Vector3(0.4, 0.6, 0.3).normalize() },
      },
      vertexShader, fragmentShader,
      side: THREE.BackSide, depthWrite: false, fog: false,
    });
    this.mesh = new THREE.Mesh(new THREE.SphereGeometry(13000, 32, 16), this.material);
    this.mesh.frustumCulled = false;
    this.mesh.renderOrder = -1;
    this.envMesh = new THREE.Mesh(new THREE.SphereGeometry(50, 32, 16), this.material);
    this.envScene.add(this.envMesh);
    this.pmrem = new THREE.PMREMGenerator(renderer);
    this.refreshEnvironment();
  }

  update(colors: SkyColors): void {
    const u = this.material.uniforms;
    (u.top.value as THREE.Color).copy(colors.top);
    (u.horizon.value as THREE.Color).copy(colors.horizon);
    (u.sunColor.value as THREE.Color).copy(colors.sun);
    (u.sunDirection.value as THREE.Vector3).copy(colors.sunDirection).normalize();
  }

  follow(camera: THREE.Camera): void {
    this.mesh.position.copy(camera.position);
  }

  environment(): THREE.Texture {
    return this.envTarget ? this.envTarget.texture : this.refreshEnvironment();
  }

  refreshEnvironment(): THREE.Texture {
    const target = this.pmrem.fromScene(this.envScene, 0, 0.1, 200);
    this.envTarget?.dispose();
    this.envTarget = target;
    return target.texture;
  }

  dispose(): void {
    this.envTarget?.dispose();
    this.envTarget = null;
    this.pmrem.dispose();
    this.mesh.geometry.dispose();
    this.envMesh.geometry.dispose();
    this.material.dispose();
  }
}
