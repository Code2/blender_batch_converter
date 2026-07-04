bl_info = {
    "name": "Batch Converter",
    "author": "Code2",
    "version": (0, 1, 1),
    "blender": (5, 0, 0),
    "location": "View3D > Sidebar > Converter Tab",
    "description": "Convert multiple 3D files in batch: FBX, OBJ, STL, glTF, GLB, ABC, PLY, DAE, BLEND",
    "category": "Import-Export",
    "doc_url": "https://github.com/yourusername/batch-converter",
    "tracker_url": "https://github.com/yourusername/batch-converter/issues",
}

import bpy
import os
import datetime

# ============================================================================
# SIMPLE LOGGER
# ============================================================================

class SimpleLogger:
    def __init__(self, output_dir):
        self.output_dir = output_dir
        self.log = []
    
    def add(self, filename, status, message):
        self.log.append(f"[{status}] {filename}: {message}")
    
    def save(self):
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(self.output_dir, f"conversion_log_{timestamp}.txt")
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("BATCH CONVERTER LOG\n")
            f.write("="*40 + "\n\n")
            for entry in self.log:
                f.write(entry + "\n")
        return filepath

# ============================================================================
# FUNZIONI DI UTILITA'
# ============================================================================

def clear_scene():
    """Pulisce completamente la scena"""
    try:
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=False)
        
        for material in bpy.data.materials:
            if not material.users:
                bpy.data.materials.remove(material)
        
        for texture in bpy.data.textures:
            if not texture.users:
                bpy.data.textures.remove(texture)
        
        for image in bpy.data.images:
            if not image.users:
                bpy.data.images.remove(image)
        
        for mesh in bpy.data.meshes:
            if not mesh.users:
                bpy.data.meshes.remove(mesh)
        
        for light in bpy.data.lights:
            if not light.users:
                bpy.data.lights.remove(light)
        
        for camera in bpy.data.cameras:
            if not camera.users:
                bpy.data.cameras.remove(camera)
        
        for action in bpy.data.actions:
            if not action.users:
                bpy.data.actions.remove(action)
                
    except Exception as e:
        print(f"Error clearing scene: {e}")

def apply_mesh_options(scene):
    """Applica le opzioni di mesh alla scena corrente"""
    mesh_objects = [obj for obj in bpy.data.objects if obj.type == 'MESH']
    if not mesh_objects:
        return False
    
    try:
        if scene.join_meshes and len(mesh_objects) > 1:
            bpy.ops.object.select_all(action='DESELECT')
            for obj in mesh_objects:
                obj.select_set(True)
            bpy.context.view_layer.objects.active = mesh_objects[0]
            bpy.ops.object.join()
            mesh_objects = [bpy.context.view_layer.objects.active]
        
        if scene.triangulate_mesh:
            for obj in mesh_objects:
                if obj.type == 'MESH':
                    bpy.context.view_layer.objects.active = obj
                    bpy.ops.object.modifier_add(type='TRIANGULATE')
                    for mod in obj.modifiers:
                        if mod.type == 'TRIANGULATE':
                            bpy.ops.object.modifier_apply(modifier=mod.name)
                            break
        
        if scene.center_pivot:
            bpy.context.scene.cursor.location = (0, 0, 0)
            for obj in mesh_objects:
                bpy.context.view_layer.objects.active = obj
                bpy.ops.object.origin_set(type='ORIGIN_CURSOR', center='MEDIAN')
                obj.location = (0, 0, 0)
        
        if scene.bake_transforms:
            for obj in mesh_objects:
                obj.location = (0, 0, 0)
                obj.rotation_euler = (0, 0, 0)
                obj.scale = (1, 1, 1)
        
        if scene.purge_orphans:
            bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
            
        return True
        
    except Exception as e:
        print(f"Optimization error: {e}")
        return False

# ============================================================================
# OPERATORS
# ============================================================================

class OBJECT_OT_choose_output_dir(bpy.types.Operator):
    bl_idname = "object.choose_output_dir"
    bl_label = "Select Output Directory"
    bl_options = {'REGISTER'}

    directory: bpy.props.StringProperty(subtype="DIR_PATH")

    def execute(self, context):
        context.scene.custom_output_dir = self.directory
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

class OBJECT_OT_select_source_folder(bpy.types.Operator):
    bl_idname = "object.select_source_folder"
    bl_label = "Select Source Folder"
    bl_options = {'REGISTER'}

    directory: bpy.props.StringProperty(subtype="DIR_PATH")

    def execute(self, context):
        context.scene.source_folder = self.directory
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

class BATCHCONVERTER_OT_start(bpy.types.Operator):
    bl_idname = "batchconverter.start"
    bl_label = "START CONVERSION"
    bl_options = {'REGISTER', 'UNDO'}

    # RIMOSSE le proprietà che causavano il file browser
    # filepath, files e directory NON servono per la modalità cartella
    
    logger = None

    def execute(self, context):
        scene = context.scene
        
        try:
            if not scene.source_folder:
                self.report({'ERROR'}, "Please select a source folder first!")
                return {'CANCELLED'}
            
            out_dir = self.get_output_dir(context)
            if out_dir:
                self.logger = SimpleLogger(out_dir)
            
            self.process_folder(context, scene.source_folder, out_dir)
            
            clear_scene()
            
            if self.logger:
                log_file = self.logger.save()
                self.report({'INFO'}, f"Log saved: {log_file}")
            
            self.report({'INFO'}, "Conversion complete! Scene cleared.")
            return {'FINISHED'}
                
        except Exception as e:
            self.report({'ERROR'}, f"Error: {str(e)}")
            return {'CANCELLED'}

    # RIMOSSO invoke() perché non serve più - eseguiamo direttamente execute()

    def process_folder(self, context, source_dir, output_dir):
        supported = {'.fbx', '.obj', '.stl', '.gltf', '.glb', '.abc', '.ply', '.dae', '.blend'}
        
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in supported:
                    input_path = os.path.join(root, file)
                    
                    if context.scene.create_subfolders:
                        rel_path = os.path.relpath(root, source_dir)
                        if rel_path != '.':
                            out_subdir = os.path.join(output_dir, rel_path)
                            os.makedirs(out_subdir, exist_ok=True)
                        else:
                            out_subdir = output_dir
                    else:
                        out_subdir = output_dir
                    
                    self.process_file(context, input_path, out_subdir)

    def process_file(self, context, input_path, output_dir):
        scene = context.scene
        filename = os.path.basename(input_path)
        name, ext = os.path.splitext(filename)
        ext = ext.lower()
        
        try:
            if filename.startswith("."):
                if self.logger:
                    self.logger.add(filename, "SKIP", "Hidden file")
                return
            
            clear_scene()
            
            # ===== IMPORT =====
            try:
                if ext == '.blend':
                    bpy.ops.wm.open_mainfile(filepath=input_path)
                elif ext == '.fbx':
                    bpy.ops.import_scene.fbx(filepath=input_path)
                elif ext == '.obj':
                    bpy.ops.wm.obj_import(filepath=input_path)
                elif ext == '.stl':
                    bpy.ops.wm.stl_import(filepath=input_path)
                elif ext in ['.gltf', '.glb']:
                    bpy.ops.import_scene.gltf(filepath=input_path)
                elif ext == '.abc':
                    bpy.ops.wm.abc_import(filepath=input_path)
                elif ext == '.ply':
                    bpy.ops.import_mesh.ply(filepath=input_path)
                elif ext == '.dae':
                    bpy.ops.import_scene.dae(filepath=input_path)
                else:
                    if self.logger:
                        self.logger.add(filename, "SKIP", f"Unsupported: {ext}")
                    return
                    
            except Exception as e:
                if self.logger:
                    self.logger.add(filename, "FAIL", f"Import error: {str(e)}")
                return
            
            mesh_objects = [obj for obj in bpy.data.objects if obj.type == 'MESH']
            if not mesh_objects:
                if self.logger:
                    self.logger.add(filename, "SKIP", "No mesh objects")
                return
            
            apply_mesh_options(scene)
            
            # ===== ESPORTA =====
            try:
                target_format = scene.target_format
                
                if target_format == '.blend':
                    output_name = f"{name}.blend"
                    output_path = os.path.join(output_dir, output_name)
                    
                    if not scene.overwrite_existing and os.path.exists(output_path):
                        base = name
                        counter = 1
                        while os.path.exists(os.path.join(output_dir, f"{base}_{counter}.blend")):
                            counter += 1
                        output_path = os.path.join(output_dir, f"{base}_{counter}.blend")
                    
                    bpy.ops.wm.save_as_mainfile(filepath=output_path)
                    
                    if self.logger:
                        self.logger.add(filename, "OK", f"Saved as .blend")
                    return
                
                output_name = f"{name}{target_format}"
                output_path = os.path.join(output_dir, output_name)
                
                if not scene.overwrite_existing and os.path.exists(output_path):
                    base, ext2 = os.path.splitext(output_name)
                    counter = 1
                    while os.path.exists(os.path.join(output_dir, f"{base}_{counter}{ext2}")):
                        counter += 1
                    output_path = os.path.join(output_dir, f"{base}_{counter}{ext2}")
                
                if target_format == '.fbx':
                    bpy.ops.export_scene.fbx(filepath=output_path)
                elif target_format == '.obj':
                    bpy.ops.wm.obj_export(filepath=output_path)
                elif target_format == '.stl':
                    bpy.ops.wm.stl_export(filepath=output_path)
                elif target_format == '.gltf':
                    bpy.ops.export_scene.gltf(filepath=output_path, export_format='GLTF_SEPARATE')
                elif target_format == '.glb':
                    bpy.ops.export_scene.gltf(filepath=output_path, export_format='GLB')
                elif target_format == '.abc':
                    bpy.ops.wm.abc_export(filepath=output_path)
                elif target_format == '.ply':
                    bpy.ops.export_mesh.ply(filepath=output_path)
                elif target_format == '.dae':
                    bpy.ops.export_scene.dae(filepath=output_path)
                else:
                    if self.logger:
                        self.logger.add(filename, "FAIL", f"Unsupported export: {target_format}")
                    return
                
                if self.logger:
                    self.logger.add(filename, "OK", f"Converted to {target_format}")
                    
            except Exception as e:
                if self.logger:
                    self.logger.add(filename, "FAIL", f"Export error: {str(e)}")
                    
        except Exception as e:
            if self.logger:
                self.logger.add(filename, "FAIL", f"Unexpected error: {str(e)}")

    def get_output_dir(self, context):
        scene = context.scene
        
        if scene.custom_output_dir:
            return scene.custom_output_dir
        
        if scene.source_folder:
            source_dir = scene.source_folder
            out_dir = os.path.join(os.path.dirname(source_dir), f"{os.path.basename(source_dir)}_converted")
            os.makedirs(out_dir, exist_ok=True)
            return out_dir
        
        return ""

# ============================================================================
# PREFERENCE PANEL
# ============================================================================

class BATCHCONVERTER_OT_preferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    def draw(self, context):
        layout = self.layout
        
        box = layout.box()
        row = box.row()
        row.scale_y = 1.5
        row.label(text="Blender Batch Converter", icon='FILE_REFRESH')
        
        box = layout.box()
        box.label(text="DESCRIPTION", icon='INFO')
        col = box.column(align=True)
        col.scale_y = 1.2
        col.label(text="Convert multiple 3D files in batch with a single click.")
        col.separator()
        col.label(text="Supported Input Formats:")
        col.label(text="  • BLEND, FBX, OBJ, STL, glTF, GLB, Alembic, PLY, Collada")
        col.separator()
        col.label(text="Supported Output Formats:")
        col.label(text="  • Blender, FBX, OBJ, STL, glTF, GLB, Alembic, PLY, Collada")
        
        box = layout.box()
        box.label(text="FEATURES", icon='SETTINGS')
        col = box.column(align=True)
        col.scale_y = 1.2
        
        row = col.row()
        row.label(text="✓", icon='CHECKMARK')
        row.label(text="Recursive folder processing (process subfolders)")
        
        row = col.row()
        row.label(text="✓", icon='CHECKMARK')
        row.label(text="Preserve folder structure on export")
        
        row = col.row()
        row.label(text="✓", icon='CHECKMARK')
        row.label(text="Join multiple meshes into one")
        
        row = col.row()
        row.label(text="✓", icon='CHECKMARK')
        row.label(text="Triangulate geometry")
        
        row = col.row()
        row.label(text="✓", icon='CHECKMARK')
        row.label(text="Center pivot at origin (0,0,0)")
        
        row = col.row()
        row.label(text="✓", icon='CHECKMARK')
        row.label(text="Bake transforms (reset location/rotation/scale)")
        
        row = col.row()
        row.label(text="✓", icon='CHECKMARK')
        row.label(text="Purge unused data (materials, textures, etc.)")
        
        row = col.row()
        row.label(text="✓", icon='CHECKMARK')
        row.label(text="Overwrite or skip existing files")
        
        row = col.row()
        row.label(text="✓", icon='CHECKMARK')
        row.label(text="Generate detailed log file (TXT)")
        
        box = layout.box()
        box.label(text="HOW TO USE", icon='QUESTION')
        col = box.column(align=True)
        col.scale_y = 1.2
        
        col.label(text="1. Select Source Folder")
        col.label(text="   → Choose the folder containing your 3D files")
        col.separator()
        
        col.label(text="2. Configure Output Settings")
        col.label(text="   → Select output format (Blender, FBX, OBJ, STL, glTF, etc.)")
        col.label(text="   → Choose to preserve folder structure")
        col.label(text="   → Set if you want to overwrite existing files")
        col.label(text="   → Select a custom output folder (optional)")
        col.separator()
        
        col.label(text="3. Configure Mesh Options (Optional)")
        col.label(text="   → Join Meshes: Combine all meshes into one")
        col.label(text="   → Triangulate: Convert quads to triangles")
        col.label(text="   → Center at Origin: Move pivot to (0,0,0)")
        col.label(text="   → Bake Transforms: Reset location/rotation/scale")
        col.label(text="   → Purge Orphans: Remove unused data")
        col.separator()
        
        col.label(text="4. Click START CONVERSION")
        col.label(text="   → All files in the source folder will be converted")
        col.label(text="   → A log file is saved in the output folder")
        
        box = layout.box()
        box.label(text="TIPS", icon='LIGHT')
        col = box.column(align=True)
        col.scale_y = 1.2
        col.label(text="• For Unreal Engine: Use FBX format with 'Bake Transforms'")
        col.label(text="• For Unity: Use FBX or glTF with 'Triangulate'")
        col.label(text="• For 3D Printing: Use STL format with 'Purge Orphans'")
        col.label(text="• For Web: Use glTF format (GLB for single file)")
        col.label(text="• For BLEND files: Convert to any format or save as new BLEND")
        
        box = layout.box()
        row = box.row()
        row.alignment = 'CENTER'
        row.label(text=f"Version {'.'.join(map(str, bl_info['version']))} | Blender {bpy.app.version_string}", icon='PACKAGE')

# ============================================================================
# UI PANEL
# ============================================================================

class VIEW3D_PT_batch_converter(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Converter'
    bl_label = 'Batch Converter'

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        
        # ===== INFO BOX =====
        box = layout.box()
        box.label(text="INFO", icon='INFO')
        col = box.column(align=True)
        col.scale_y = 0.8
        col.label(text="Converts multiple files in a folder")
        col.label(text="Supports: BLEND, FBX, OBJ, STL, glTF, GLB, ABC, PLY, DAE")
        col.label(text="Output: Blender, FBX, OBJ, STL, glTF, GLB, ABC, PLY, DAE")
        col.separator()
        col.label(text="1. Select Source Folder")
        col.label(text="2. Choose Output Format")
        col.label(text="3. Click START CONVERSION")
        col.label(text="A log file is saved in the output folder")
        
        # ===== INPUT SOURCE =====
        box = layout.box()
        box.label(text="Input Source", icon='FILE_FOLDER')
        
        box.operator("object.select_source_folder", text="Select Source Folder", icon='FILEBROWSER')
        
        if scene.source_folder:
            path = scene.source_folder
            if len(path) > 60:
                path = "..." + path[-57:]
            box.label(text=f"Source: {path}", icon='CHECKMARK')
        else:
            box.label(text="No folder selected", icon='ERROR')
        
        # ===== OUTPUT SETTINGS =====
        box = layout.box()
        box.label(text="Output Settings", icon='EXPORT')
        box.prop(scene, "target_format", text="Format")
        box.prop(scene, "create_subfolders", text="Preserve Folder Structure")
        box.prop(scene, "overwrite_existing", text="Overwrite Existing")
        
        box.operator("object.choose_output_dir", text="Browse Output Folder", icon='FILEBROWSER')
        if scene.custom_output_dir:
            path = scene.custom_output_dir
            if len(path) > 60:
                path = "..." + path[-57:]
            box.label(text=f"Output: {path}", icon='CHECKMARK')
        else:
            box.label(text="(will use source folder + '_converted')", icon='INFO')
        
        # ===== MESH OPTIONS =====
        box = layout.box()
        box.label(text="Mesh Options", icon='MESH_DATA')
        box.prop(scene, "join_meshes", text="Join Meshes")
        box.prop(scene, "triangulate_mesh", text="Triangulate")
        box.prop(scene, "center_pivot", text="Center at Origin")
        box.prop(scene, "bake_transforms", text="Bake Transforms")
        box.prop(scene, "purge_orphans", text="Purge Orphans")
        
        # ===== START BUTTON =====
        layout.separator()
        row = layout.row(align=True)
        row.scale_y = 2.0
        row.operator("batchconverter.start", text="START CONVERSION", icon='PLAY')

# ============================================================================
# REGISTRATION
# ============================================================================

# Formati disponibili - LISTA FISSA
FORMAT_ITEMS = [
    ('.blend', 'Blender', 'Native Blender format'),
    ('.fbx', 'FBX', 'Autodesk FBX'),
    ('.obj', 'OBJ', 'Wavefront OBJ'),
    ('.stl', 'STL', 'Stereolithography'),
    ('.gltf', 'glTF', 'glTF 2.0'),
    ('.glb', 'GLB', 'glTF 2.0 Binary'),
    ('.abc', 'Alembic', 'Alembic Cache'),
    ('.ply', 'PLY', 'Stanford PLY'),
    ('.dae', 'Collada', 'Collada DAE'),
]

def register():
    bpy.utils.register_class(OBJECT_OT_choose_output_dir)
    bpy.utils.register_class(OBJECT_OT_select_source_folder)
    bpy.utils.register_class(BATCHCONVERTER_OT_start)
    bpy.utils.register_class(VIEW3D_PT_batch_converter)
    bpy.utils.register_class(BATCHCONVERTER_OT_preferences)
    
    # Properties
    bpy.types.Scene.target_format = bpy.props.EnumProperty(
        name="Format",
        items=FORMAT_ITEMS,
        default='.fbx',
        description="Output format for conversion"
    )
    
    bpy.types.Scene.source_folder = bpy.props.StringProperty(
        name="Source Folder", subtype="DIR_PATH"
    )
    bpy.types.Scene.create_subfolders = bpy.props.BoolProperty(
        name="Preserve Structure", default=False
    )
    bpy.types.Scene.overwrite_existing = bpy.props.BoolProperty(
        name="Overwrite", default=True
    )
    bpy.types.Scene.custom_output_dir = bpy.props.StringProperty(
        name="Output Directory", subtype="DIR_PATH"
    )
    bpy.types.Scene.join_meshes = bpy.props.BoolProperty(
        name="Join Meshes", default=False
    )
    bpy.types.Scene.triangulate_mesh = bpy.props.BoolProperty(
        name="Triangulate", default=False
    )
    bpy.types.Scene.center_pivot = bpy.props.BoolProperty(
        name="Center at Origin", default=False
    )
    bpy.types.Scene.bake_transforms = bpy.props.BoolProperty(
        name="Bake Transforms", default=False
    )
    bpy.types.Scene.purge_orphans = bpy.props.BoolProperty(
        name="Purge Orphans", default=False
    )

def unregister():
    try:
        bpy.utils.unregister_class(OBJECT_OT_choose_output_dir)
    except:
        pass
    try:
        bpy.utils.unregister_class(OBJECT_OT_select_source_folder)
    except:
        pass
    try:
        bpy.utils.unregister_class(BATCHCONVERTER_OT_start)
    except:
        pass
    try:
        bpy.utils.unregister_class(VIEW3D_PT_batch_converter)
    except:
        pass
    try:
        bpy.utils.unregister_class(BATCHCONVERTER_OT_preferences)
    except:
        pass
    
    props = [
        'target_format', 'source_folder', 'create_subfolders',
        'overwrite_existing', 'custom_output_dir',
        'join_meshes', 'triangulate_mesh', 'center_pivot', 'bake_transforms',
        'purge_orphans'
    ]
    for prop in props:
        try:
            delattr(bpy.types.Scene, prop)
        except:
            pass

if __name__ == "__main__":
    register()