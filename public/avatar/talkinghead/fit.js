import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
const renderer=new THREE.WebGLRenderer({antialias:true});renderer.setPixelRatio(1);renderer.setSize(innerWidth,innerHeight);document.body.append(renderer.domElement);renderer.setClearColor('#777777');renderer.outputColorSpace=THREE.SRGBColorSpace;
const scene=new THREE.Scene();scene.add(new THREE.HemisphereLight(0xffffff,0x999999,2));const light=new THREE.DirectionalLight(0xffffff,2);light.position.set(0,2,3);scene.add(light);
const aspect=innerWidth/innerHeight, half=.2;const camera=new THREE.OrthographicCamera(-half*aspect,half*aspect,half,-half,.1,10);camera.position.set(0,1.60,2);camera.lookAt(0,1.60,0);
const human=new URLSearchParams(location.search).get('model')==='human';
const gltf=await new GLTFLoader().loadAsync(human?'realistic-base.glb':'reference.glb');scene.add(gltf.scene);gltf.scene.traverse(o=>{if(['Wolf3D_Glasses','Wolf3D_Hair','Human.ponytail01'].includes(o.name))o.visible=false;});renderer.render(scene,camera);document.body.dataset.ready='true';
